import frappe
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from wood_factory.accounting import post_operating_cost, resolve_accounting_context


def get_worker_hourly_rate(user, company, workstation=None, effective_date=None):
    rate = 0
    effective_date = effective_date or nowdate()
    if user and frappe.db.exists("DocType", "Factory Worker Cost Rate"):
        rows = frappe.get_all(
            "Factory Worker Cost Rate",
            filters={"user": user, "company": company, "active": 1, "effective_from": ["<=", effective_date]},
            fields=["hourly_cost"],
            order_by="effective_from desc, modified desc",
            limit_page_length=1,
        )
        if rows:
            rate = flt(rows[0].hourly_cost)
    if rate <= 0 and workstation:
        rate = flt(frappe.db.get_value("Factory Workstation", workstation, "default_labor_hourly_cost"))
    return flt(rate, 2)


def get_workstation_costing(workstation):
    if not workstation:
        return frappe._dict({
            "track_labor_cost": 0,
            "track_machine_cost": 0,
            "default_labor_hourly_cost": 0,
            "machine_hourly_cost": 0,
            "company": None,
        })
    values = frappe.db.get_value(
        "Factory Workstation",
        workstation,
        ["track_labor_cost", "track_machine_cost", "default_labor_hourly_cost", "machine_hourly_cost", "company"],
        as_dict=True,
    )
    return values or frappe._dict()


def _use_posted_values(ledger, rate, amount):
    if not ledger or ledger.status != "Posted":
        return flt(rate, 2), flt(amount, 2)
    return flt(ledger.hourly_rate, 2), flt(ledger.amount, 2)


def post_order_stage_cost(factory_order, stage_row_name):
    order = frappe.get_doc("Factory Order", factory_order) if isinstance(factory_order, str) else factory_order
    row = next((item for item in order.production_stages if item.name == stage_row_name), None)
    if not row or row.status != "Completed":
        return {"status": "Skipped", "reason": "Stage is not completed"}

    workstation = get_workstation_costing(row.workstation)
    company = order.company or workstation.get("company") or resolve_accounting_context(order).company
    labor_rate = get_worker_hourly_rate(row.responsible, company, row.workstation, getdate(row.completed_at) if row.completed_at else None) if cint(workstation.get("track_labor_cost")) else 0
    machine_rate = flt(workstation.get("machine_hourly_cost"), 2) if cint(workstation.get("track_machine_cost")) else 0
    minutes = flt(row.actual_minutes, 2)
    labor_cost = flt(minutes / 60 * labor_rate, 2)
    machine_cost = flt(minutes / 60 * machine_rate, 2)
    internal_rework = cint(row.get("internal_rework"))

    labor_ledger = post_operating_cost(
        factory_order=order.name,
        transaction_key=f"Factory Order Stage|{row.name}|Labor",
        transaction_type="Labor Cost",
        amount=labor_cost,
        expense_kind="labor",
        internal_rework=internal_rework,
        factory_order_stage=row.name,
        production_stage=row.stage,
        workstation=row.workstation,
        responsible=row.responsible,
        actual_minutes=minutes,
        hourly_rate=labor_rate,
        remarks=f"Actual labor cost for {row.stage} on Factory Order {order.name}",
    )
    machine_ledger = post_operating_cost(
        factory_order=order.name,
        transaction_key=f"Factory Order Stage|{row.name}|Machine",
        transaction_type="Machine Cost",
        amount=machine_cost,
        expense_kind="machine",
        internal_rework=internal_rework,
        factory_order_stage=row.name,
        production_stage=row.stage,
        workstation=row.workstation,
        responsible=row.responsible,
        actual_minutes=minutes,
        hourly_rate=machine_rate,
        remarks=f"Actual machine cost for {row.stage} on Factory Order {order.name}",
    )
    labor_rate, labor_cost = _use_posted_values(labor_ledger, labor_rate, labor_cost)
    machine_rate, machine_cost = _use_posted_values(machine_ledger, machine_rate, machine_cost)

    missing = []
    if cint(workstation.get("track_labor_cost")) and labor_rate <= 0:
        missing.append("labor rate")
    if cint(workstation.get("track_machine_cost")) and machine_rate <= 0:
        missing.append("machine rate")
    if labor_cost > 0 and not labor_ledger:
        missing.append("labor cost ledger")
    if machine_cost > 0 and not machine_ledger:
        missing.append("machine cost ledger")
    costing_status = "Partial" if missing else "Posted"
    frappe.db.set_value(
        "Factory Order Stage",
        row.name,
        {
            "labor_hourly_rate": labor_rate,
            "machine_hourly_rate": machine_rate,
            "labor_cost": labor_cost,
            "machine_cost": machine_cost,
            "costing_status": costing_status,
        },
        update_modified=False,
    )
    totals = sync_factory_order_actual_costs(order.name)
    return {
        "status": costing_status,
        "labor_cost": labor_cost,
        "machine_cost": machine_cost,
        "labor_ledger": labor_ledger.name if labor_ledger else None,
        "machine_ledger": machine_ledger.name if machine_ledger else None,
        "missing": missing,
        "totals": totals,
    }


def post_exception_piece_stage_cost(piece, stage, minutes, workstation, responsible, costed_on=None):
    piece_doc = frappe.get_doc("Factory Piece", piece) if isinstance(piece, str) else piece
    exception = frappe.db.get_value("Piece Exception", {"replacement_piece": piece_doc.name}, "name") or frappe.db.get_value(
        "Piece Exception",
        {"factory_piece": piece_doc.name, "status": ["not in", ["Resolved", "Cancelled"]]},
        "name",
    )
    workstation_costing = get_workstation_costing(workstation)
    order = frappe.get_doc("Factory Order", piece_doc.factory_order)
    company = order.company or workstation_costing.get("company") or resolve_accounting_context(order, internal_replacement=True).company
    rate_date = getdate(costed_on) if costed_on else nowdate()
    labor_rate = get_worker_hourly_rate(responsible, company, workstation, rate_date) if cint(workstation_costing.get("track_labor_cost")) else 0
    machine_rate = flt(workstation_costing.get("machine_hourly_cost"), 2) if cint(workstation_costing.get("track_machine_cost")) else 0
    minutes = flt(minutes, 2)
    labor_cost = flt(minutes / 60 * labor_rate, 2)
    machine_cost = flt(minutes / 60 * machine_rate, 2)

    labor_ledger = post_operating_cost(
        factory_order=piece_doc.factory_order,
        transaction_key=f"Factory Piece|{piece_doc.name}|{stage}|Labor",
        transaction_type="Labor Cost",
        amount=labor_cost,
        expense_kind="labor",
        internal_rework=True,
        factory_piece=piece_doc.name,
        piece_exception=exception,
        production_stage=stage,
        workstation=workstation,
        responsible=responsible,
        actual_minutes=minutes,
        hourly_rate=labor_rate,
        remarks=f"Factory-funded replacement labor for {piece_doc.name} at {stage}",
    )
    machine_ledger = post_operating_cost(
        factory_order=piece_doc.factory_order,
        transaction_key=f"Factory Piece|{piece_doc.name}|{stage}|Machine",
        transaction_type="Machine Cost",
        amount=machine_cost,
        expense_kind="machine",
        internal_rework=True,
        factory_piece=piece_doc.name,
        piece_exception=exception,
        production_stage=stage,
        workstation=workstation,
        responsible=responsible,
        actual_minutes=minutes,
        hourly_rate=machine_rate,
        remarks=f"Factory-funded replacement machine cost for {piece_doc.name} at {stage}",
    )
    labor_rate, labor_cost = _use_posted_values(labor_ledger, labor_rate, labor_cost)
    machine_rate, machine_cost = _use_posted_values(machine_ledger, machine_rate, machine_cost)

    missing = []
    if cint(workstation_costing.get("track_labor_cost")) and labor_rate <= 0:
        missing.append("labor rate")
    if cint(workstation_costing.get("track_machine_cost")) and machine_rate <= 0:
        missing.append("machine rate")
    if labor_cost > 0 and not labor_ledger:
        missing.append("labor cost ledger")
    if machine_cost > 0 and not machine_ledger:
        missing.append("machine cost ledger")
    status = "Partial" if missing else "Posted"
    event = _upsert_piece_stage_cost(
        piece_doc=piece_doc,
        exception=exception,
        stage=stage,
        workstation=workstation,
        responsible=responsible,
        minutes=minutes,
        labor_rate=labor_rate,
        machine_rate=machine_rate,
        labor_cost=labor_cost,
        machine_cost=machine_cost,
        status=status,
        missing=missing,
        costed_on=costed_on,
    )
    cumulative_status = _sync_piece_costing_status(piece_doc.name)
    sync_factory_order_actual_costs(piece_doc.factory_order)
    return {
        "status": status,
        "cumulative_status": cumulative_status,
        "stage_cost_event": event.name,
        "labor_cost": labor_cost,
        "machine_cost": machine_cost,
        "labor_ledger": labor_ledger.name if labor_ledger else None,
        "machine_ledger": machine_ledger.name if machine_ledger else None,
        "missing": missing,
    }


def recalculate_exception_piece_costs(factory_order):
    if not frappe.db.exists("DocType", "Factory Piece Stage Cost"):
        return []
    events = frappe.get_all(
        "Factory Piece Stage Cost",
        filters={"factory_order": factory_order, "costing_status": ["in", ["Pending", "Partial"]]},
        fields=["factory_piece", "production_stage", "actual_minutes", "workstation", "responsible", "costed_on"],
        order_by="costed_on asc",
    )
    results = []
    for event in events:
        result = post_exception_piece_stage_cost(
            piece=event.factory_piece,
            stage=event.production_stage,
            minutes=event.actual_minutes,
            workstation=event.workstation,
            responsible=event.responsible,
            costed_on=event.costed_on,
        )
        results.append({"factory_piece": event.factory_piece, "stage": event.production_stage, **result})
    return results


def _upsert_piece_stage_cost(piece_doc, exception, stage, workstation, responsible, minutes, labor_rate, machine_rate, labor_cost, machine_cost, status, missing, costed_on=None):
    key = f"Factory Piece|{piece_doc.name}|{stage}"
    name = frappe.db.get_value("Factory Piece Stage Cost", {"event_key": key}, "name")
    values = {
        "factory_order": piece_doc.factory_order,
        "piece_exception": exception,
        "factory_piece": piece_doc.name,
        "production_stage": stage,
        "workstation": workstation,
        "responsible": responsible,
        "actual_minutes": flt(minutes, 2),
        "labor_hourly_rate": flt(labor_rate, 2),
        "machine_hourly_rate": flt(machine_rate, 2),
        "labor_cost": flt(labor_cost, 2),
        "machine_cost": flt(machine_cost, 2),
        "costing_status": status,
        "costed_on": costed_on or now_datetime(),
        "missing_details": ", ".join(missing),
    }
    if name:
        doc = frappe.get_doc("Factory Piece Stage Cost", name)
        doc.flags.factory_cost_update = True
        doc.update(values)
        doc.save(ignore_permissions=True)
        return doc
    doc = frappe.new_doc("Factory Piece Stage Cost")
    doc.update({"event_key": key, **values})
    doc.flags.factory_cost_insert = True
    doc.insert(ignore_permissions=True)
    return doc


def _sync_piece_costing_status(factory_piece):
    rows = frappe.get_all(
        "Factory Piece Stage Cost",
        filters={"factory_piece": factory_piece},
        fields=["costing_status"],
    ) if frappe.db.exists("DocType", "Factory Piece Stage Cost") else []
    if not rows:
        status = "Pending"
    elif any(row.costing_status != "Posted" for row in rows):
        status = "Partial"
    else:
        status = "Posted"
    frappe.db.set_value("Factory Piece", factory_piece, "costing_status", status, update_modified=False)
    return status


def sync_factory_order_actual_costs(factory_order):
    if not frappe.db.exists("Factory Order", factory_order):
        return {}
    rows = frappe.get_all(
        "Factory Cost Ledger",
        filters={"factory_order": factory_order, "status": "Posted"},
        fields=["transaction_type", "amount", "customer_billable", "cutting_order"],
    ) if frappe.db.exists("DocType", "Factory Cost Ledger") else []

    def total(transaction_type=None, billable=None):
        return flt(sum(
            flt(row.amount)
            for row in rows
            if (transaction_type is None or row.transaction_type == transaction_type)
            and (billable is None or cint(row.customer_billable) == cint(billable))
        ), 2)

    customer_material = total("Customer Material Consumption", 1)
    internal_new_material = total("Internal Replacement Material", 0)
    remnant_material = total("Remnant Material Consumption", 0)
    remnant_recovery_signed = total("Remnant Recovery", 0)
    remnant_recovery = abs(min(remnant_recovery_signed, 0))
    rework_material = flt(internal_new_material + remnant_material, 2)
    customer_labor = total("Labor Cost", 1)
    rework_labor = total("Labor Cost", 0)
    customer_machine = total("Machine Cost", 1)
    rework_machine = total("Machine Cost", 0)
    customer_cost = total(billable=1)
    factory_error_cost = total(billable=0)
    actual_total = total()

    gross_unused_cost = 0
    for row in rows:
        if row.transaction_type not in ("Customer Material Consumption", "Internal Replacement Material") or not row.cutting_order:
            continue
        waste_percent = flt(frappe.db.get_value("Cutting Order", row.cutting_order, "waste_percent"))
        gross_unused_cost += flt(row.amount) * waste_percent / 100
    net_waste_cost = max(gross_unused_cost - remnant_recovery, 0)

    stage_rows = frappe.get_all(
        "Factory Order Stage",
        filters={"parent": factory_order},
        fields=["status", "costing_status"],
        order_by="idx asc",
    )
    completed = [row for row in stage_rows if row.status == "Completed"]
    exception_partial = frappe.db.count(
        "Factory Piece",
        {"factory_order": factory_order, "is_exception": 1, "costing_status": "Partial"},
    ) if frappe.db.exists("DocType", "Factory Piece") else 0
    if exception_partial or (completed and any((row.costing_status or "Pending") != "Posted" for row in completed)):
        costing_status = "Partial"
    elif stage_rows and all(row.status in ("Completed", "Skipped") for row in stage_rows):
        costing_status = "Complete"
    elif rows or completed:
        costing_status = "In Progress"
    else:
        costing_status = "Not Started"

    values = {
        "customer_material_cost": customer_material,
        "internal_rework_material_cost": rework_material,
        "remnant_recovery_value": flt(remnant_recovery, 2),
        "total_posted_material_cost": flt(customer_material + rework_material - remnant_recovery, 2),
        "customer_labor_cost": customer_labor,
        "internal_rework_labor_cost": rework_labor,
        "customer_machine_cost": customer_machine,
        "internal_rework_machine_cost": rework_machine,
        "total_labor_cost": flt(customer_labor + rework_labor, 2),
        "total_machine_cost": flt(customer_machine + rework_machine, 2),
        "waste_cost_within_material": flt(net_waste_cost, 2),
        "customer_attributable_cost": customer_cost,
        "factory_error_cost": factory_error_cost,
        "total_actual_cost": actual_total,
        "costing_status": costing_status,
        "last_costing_calculation": now_datetime(),
        "accounting_status": "Posted" if rows else "Not Posted",
    }
    available = {field.fieldname for field in frappe.get_meta("Factory Order").fields}
    frappe.db.set_value(
        "Factory Order",
        factory_order,
        {key: value for key, value in values.items() if key in available},
        update_modified=False,
    )
    return values
