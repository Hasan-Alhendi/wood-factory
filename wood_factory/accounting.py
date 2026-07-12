import frappe
from frappe.utils import cint, flt, now_datetime


DEFAULT_SETTINGS = {
    "enabled": 0,
    "company": None,
    "customer_cost_center": None,
    "internal_rework_cost_center": None,
    "material_expense_account": None,
    "internal_rework_expense_account": None,
    "default_project": None,
    "require_cost_center": 1,
    "create_cost_ledger": 1,
}


def get_accounting_settings():
    settings = frappe._dict(DEFAULT_SETTINGS.copy())
    if not frappe.db.exists("DocType", "Factory Accounting Settings"):
        return settings
    stored = frappe.get_single("Factory Accounting Settings")
    for key in DEFAULT_SETTINGS:
        value = stored.get(key)
        if value is not None:
            settings[key] = value
    return settings


def resolve_accounting_context(factory_order, internal_replacement=False):
    order = frappe.get_doc("Factory Order", factory_order) if isinstance(factory_order, str) else factory_order
    settings = get_accounting_settings()
    sales_order_company = frappe.db.get_value("Sales Order", order.sales_order, "company") if order.sales_order else None
    company = order.get("company") or sales_order_company or settings.company
    if not company:
        frappe.throw("Company is required before posting factory material consumption")
    if settings.company and settings.company != company:
        frappe.throw(f"Factory Accounting Settings use {settings.company}, but Factory Order {order.name} uses {company}")

    if internal_replacement:
        cost_center = order.get("rework_cost_center") or settings.internal_rework_cost_center
        expense_account = settings.internal_rework_expense_account
        cost_owner = "Factory Internal Rework"
    else:
        cost_center = order.get("cost_center") or settings.customer_cost_center
        expense_account = settings.material_expense_account
        cost_owner = f"Customer Order {order.name}"

    project = order.get("project") or settings.default_project
    if cint(settings.enabled):
        if cint(settings.require_cost_center) and not cost_center:
            frappe.throw("Configure the required factory Cost Center in Factory Accounting Settings or Factory Order")
        if not expense_account:
            frappe.throw("Configure the material Expense Account in Factory Accounting Settings")
        _validate_dimension_company("Cost Center", cost_center, company)
        _validate_dimension_company("Account", expense_account, company)
        _validate_dimension_company("Project", project, company)

    return frappe._dict({
        "enabled": cint(settings.enabled),
        "company": company,
        "cost_center": cost_center,
        "expense_account": expense_account,
        "project": project,
        "currency": frappe.db.get_value("Company", company, "default_currency") or "USD",
        "cost_owner": cost_owner,
        "customer_billable": 0 if internal_replacement else 1,
        "create_cost_ledger": cint(settings.create_cost_ledger),
    })


def apply_stock_entry_context(stock_entry, context):
    _set_if_field(stock_entry, "company", context.company)
    _set_if_field(stock_entry, "project", context.project)
    _set_if_field(stock_entry, "cost_center", context.cost_center)


def append_material_issue_item(stock_entry, requirement, context):
    row = stock_entry.append("items", {
        "item_code": requirement["item_code"],
        "s_warehouse": requirement["warehouse"],
        "qty": requirement["qty"],
        "uom": requirement["uom"],
        "stock_uom": requirement["uom"],
        "conversion_factor": 1,
    })
    _set_if_field(row, "expense_account", context.expense_account)
    _set_if_field(row, "cost_center", context.cost_center)
    _set_if_field(row, "project", context.project)
    return row


def post_material_cost(factory_order, cutting_order, stock_entry, piece_exception=None, internal_replacement=False):
    context = resolve_accounting_context(factory_order, internal_replacement=internal_replacement)
    amount = get_stock_entry_value(stock_entry)
    transaction_type = "Internal Replacement Material" if internal_replacement else "Customer Material Consumption"
    ledger = None
    if context.create_cost_ledger:
        ledger = _create_cost_ledger(
            transaction_key=f"Stock Entry|{stock_entry.name}",
            factory_order=factory_order,
            cutting_order=cutting_order,
            piece_exception=piece_exception,
            transaction_type=transaction_type,
            context=context,
            amount=amount,
            accounting_document_type="Stock Entry",
            accounting_document=stock_entry.name,
            remarks=stock_entry.remarks,
        )
    sync_factory_order_material_totals(factory_order)
    return {"amount": amount, "currency": context.currency, "cost_ledger": ledger.name if ledger else None, "context": context}


def get_stock_entry_value(stock_entry):
    doc = frappe.get_doc("Stock Entry", stock_entry) if isinstance(stock_entry, str) else stock_entry
    for fieldname in ("total_outgoing_value", "total_amount", "value_difference"):
        value = flt(doc.get(fieldname))
        if value > 0:
            return flt(value, 2)
    total = 0
    for row in doc.items or []:
        amount = flt(row.get("basic_amount") or row.get("amount"))
        if not amount:
            qty = flt(row.get("transfer_qty") or row.get("qty"))
            amount = qty * flt(row.get("valuation_rate") or row.get("basic_rate"))
        total += amount
    return flt(abs(total), 2)


def sync_factory_order_material_totals(factory_order):
    if not frappe.db.exists("Factory Order", factory_order):
        return
    rows = frappe.get_all(
        "Factory Cost Ledger",
        filters={"factory_order": factory_order, "status": "Posted", "transaction_type": ["in", ["Customer Material Consumption", "Internal Replacement Material"]]},
        fields=["transaction_type", "amount"],
    ) if frappe.db.exists("DocType", "Factory Cost Ledger") else []
    customer_cost = sum(flt(row.amount) for row in rows if row.transaction_type == "Customer Material Consumption")
    rework_cost = sum(flt(row.amount) for row in rows if row.transaction_type == "Internal Replacement Material")
    values = {
        "customer_material_cost": flt(customer_cost, 2),
        "internal_rework_material_cost": flt(rework_cost, 2),
        "total_posted_material_cost": flt(customer_cost + rework_cost, 2),
        "accounting_status": "Posted" if rows else "Not Posted",
    }
    available = {field.fieldname for field in frappe.get_meta("Factory Order").fields}
    frappe.db.set_value("Factory Order", factory_order, {key: value for key, value in values.items() if key in available}, update_modified=False)


def on_stock_entry_cancel(doc, method=None):
    if not frappe.db.exists("DocType", "Factory Cost Ledger"):
        return
    ledgers = frappe.get_all(
        "Factory Cost Ledger",
        filters={"accounting_document_type": "Stock Entry", "accounting_document": doc.name, "status": "Posted"},
        fields=["name", "factory_order"],
    )
    affected_orders = set()
    for row in ledgers:
        frappe.db.set_value("Factory Cost Ledger", row.name, "status", "Reversed", update_modified=False)
        affected_orders.add(row.factory_order)
    for factory_order in affected_orders:
        sync_factory_order_material_totals(factory_order)


def _create_cost_ledger(transaction_key, factory_order, transaction_type, context, amount, accounting_document_type=None, accounting_document=None, cutting_order=None, piece_exception=None, remarks=None):
    existing = frappe.db.get_value("Factory Cost Ledger", {"transaction_key": transaction_key}, "name")
    if existing:
        return frappe.get_doc("Factory Cost Ledger", existing)
    doc = frappe.new_doc("Factory Cost Ledger")
    doc.update({
        "transaction_key": transaction_key,
        "factory_order": factory_order,
        "cutting_order": cutting_order,
        "piece_exception": piece_exception,
        "transaction_type": transaction_type,
        "company": context.company,
        "cost_center": context.cost_center,
        "project": context.project,
        "expense_account": context.expense_account,
        "amount": flt(amount, 2),
        "currency": context.currency,
        "customer_billable": context.customer_billable,
        "status": "Posted",
        "accounting_document_type": accounting_document_type,
        "accounting_document": accounting_document,
        "posted_on": now_datetime(),
        "remarks": remarks,
    })
    doc.flags.factory_cost_insert = True
    doc.insert(ignore_permissions=True)
    return doc


def _set_if_field(doc, fieldname, value):
    if value and doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _validate_dimension_company(doctype, name, company):
    if not name:
        return
    dimension_company = frappe.db.get_value(doctype, name, "company")
    if dimension_company and dimension_company != company:
        frappe.throw(f"{doctype} {name} belongs to {dimension_company}, not {company}")
