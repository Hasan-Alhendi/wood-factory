from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe.utils import add_days, add_to_date, cint, flt, now_datetime, nowdate

from wood_factory.security import (
    FACTORY_ACCOUNTANT,
    FACTORY_ASSEMBLY_OPERATOR,
    FACTORY_CUTTING_OPERATOR,
    FACTORY_DELIVERY_USER,
    FACTORY_DRILLING_OPERATOR,
    FACTORY_EDGE_OPERATOR,
    FACTORY_PACKING_OPERATOR,
    FACTORY_PLANNER,
    FACTORY_QUALITY_INSPECTOR,
    FACTORY_SUPERVISOR,
    require_management,
)

DEMO_TAG = "[WOOD_FACTORY_DEMO]"
DEMO_PREFIX = "WF-DEMO"
BOARD_WIDTH_MM = 1220
BOARD_HEIGHT_MM = 2440
STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")


@dataclass(frozen=True)
class Scenario:
    code: str
    customer: str
    revenue: float
    delivery_offset: int
    board_item: str
    current_stage: str | None
    stage_status: str | None
    completed_stages: int
    history_days: int
    description: str
    exception_mode: str | None = None
    ready_for_delivery: bool = False
    delivered: bool = False


SCENARIOS = (
    Scenario(
        code="NORMAL-CUTTING",
        customer="DEMO - Al Noor Kitchens",
        revenue=1850,
        delivery_offset=5,
        board_item=f"{DEMO_PREFIX}-MDF-WHITE-18",
        current_stage="Cutting",
        stage_status="Ready",
        completed_stages=0,
        history_days=0,
        description="Normal customer order waiting for cutting.",
    ),
    Scenario(
        code="DELAYED-BLOCKED",
        customer="DEMO - Al Madina Showroom",
        revenue=2750,
        delivery_offset=-3,
        board_item=f"{DEMO_PREFIX}-MDF-OAK-18",
        current_stage="Edge Banding",
        stage_status="Blocked",
        completed_stages=1,
        history_days=4,
        description="Late order blocked in edge banding because a machine is unavailable.",
    ),
    Scenario(
        code="DAMAGED-REMNANT",
        customer="DEMO - Horizon Interiors",
        revenue=1450,
        delivery_offset=2,
        board_item=f"{DEMO_PREFIX}-MDF-WHITE-18",
        current_stage="Quality Inspection",
        stage_status="Ready",
        completed_stages=4,
        history_days=6,
        description="Damaged piece found at quality inspection; replacement uses a matching remnant.",
        exception_mode="remnant",
    ),
    Scenario(
        code="WRONG-DIM-NEW-BOARD",
        customer="DEMO - Damascus Decor",
        revenue=3200,
        delivery_offset=1,
        board_item=f"{DEMO_PREFIX}-MDF-OAK-18",
        current_stage="Assembly",
        stage_status="In Progress",
        completed_stages=3,
        history_days=5,
        description="Wrong-dimension piece requires a factory-funded replacement from a new board.",
        exception_mode="new_board",
    ),
    Scenario(
        code="READY-DELIVERY",
        customer="DEMO - Modern Kitchen Center",
        revenue=2100,
        delivery_offset=0,
        board_item=f"{DEMO_PREFIX}-MDF-WHITE-18",
        current_stage=None,
        stage_status=None,
        completed_stages=6,
        history_days=10,
        description="Completed order waiting for delivery confirmation.",
        ready_for_delivery=True,
    ),
    Scenario(
        code="DELIVERED",
        customer="DEMO - Elegant Woodworks",
        revenue=2400,
        delivery_offset=-7,
        board_item=f"{DEMO_PREFIX}-MDF-OAK-18",
        current_stage=None,
        stage_status=None,
        completed_stages=6,
        history_days=18,
        description="Historically completed and delivered order used by profitability reports.",
        ready_for_delivery=True,
        delivered=True,
    ),
)

USER_DEFINITIONS = {
    "supervisor": ("wf.demo.supervisor@example.com", "Demo Factory Supervisor", FACTORY_SUPERVISOR, 6.5),
    "planner": ("wf.demo.planner@example.com", "Demo Factory Planner", FACTORY_PLANNER, 6.0),
    "accountant": ("wf.demo.accountant@example.com", "Demo Factory Accountant", FACTORY_ACCOUNTANT, 6.0),
    "Cutting": ("wf.demo.cutting@example.com", "Demo Cutting Worker", FACTORY_CUTTING_OPERATOR, 4.5),
    "Edge Banding": ("wf.demo.edging@example.com", "Demo Edge Banding Worker", FACTORY_EDGE_OPERATOR, 4.2),
    "Drilling": ("wf.demo.drilling@example.com", "Demo Drilling Worker", FACTORY_DRILLING_OPERATOR, 4.4),
    "Assembly": ("wf.demo.assembly@example.com", "Demo Assembly Worker", FACTORY_ASSEMBLY_OPERATOR, 4.0),
    "Quality Inspection": ("wf.demo.quality@example.com", "Demo Quality Inspector", FACTORY_QUALITY_INSPECTOR, 5.0),
    "Packing": ("wf.demo.packing@example.com", "Demo Packing Worker", FACTORY_PACKING_OPERATOR, 3.8),
    "delivery": ("wf.demo.delivery@example.com", "Demo Delivery User", FACTORY_DELIVERY_USER, 3.8),
}

WORKSTATION_DEFINITIONS = (
    ("DEMO Panel Saw 1", "Cutting", "Active", 480, 92, 4.5, 8.0, None),
    ("DEMO Panel Saw 2", "Cutting", "Active", 420, 85, 4.5, 6.5, None),
    ("DEMO Edge Bander 1", "Edge Banding", "Active", 450, 90, 4.2, 7.0, None),
    ("DEMO Edge Bander 2", "Edge Banding", "Maintenance", 450, 90, 4.2, 7.0, "Scheduled maintenance for demo bottleneck"),
    ("DEMO CNC Drill", "Drilling", "Active", 420, 88, 4.4, 9.0, None),
    ("DEMO Assembly Bench", "Assembly", "Active", 480, 82, 4.0, 2.0, None),
    ("DEMO Quality Station", "Quality Inspection", "Active", 480, 95, 5.0, 0.0, None),
    ("DEMO Packing Line", "Packing", "Active", 480, 90, 3.8, 1.5, None),
)

PART_TEMPLATES = (
    {"part_name": "Tall Door", "width_mm": 450, "height_mm": 2100, "qty": 2, "allow_rotation": 0, "grain_direction": "Along Height", "edges": (1, 1, 1, 1)},
    {"part_name": "Wall Cabinet Door", "width_mm": 600, "height_mm": 720, "qty": 4, "allow_rotation": 1, "grain_direction": "Any", "edges": (1, 1, 1, 1)},
    {"part_name": "Drawer Front", "width_mm": 720, "height_mm": 220, "qty": 3, "allow_rotation": 1, "grain_direction": "Any", "edges": (1, 1, 1, 1)},
    {"part_name": "Side Panel", "width_mm": 560, "height_mm": 720, "qty": 2, "allow_rotation": 1, "grain_direction": "Along Height", "edges": (1, 0, 1, 0)},
)


@frappe.whitelist()
def get_demo_status(company=None):
    require_management()
    company = _resolve_company(company)
    return _status(company)


@frappe.whitelist()
def create_demo_dataset(company=None, include_users=1, include_stock=1):
    """Create a realistic, non-destructive and idempotent factory dataset.

    Demo users are disabled and never receive welcome email. Material receipts are
    created only once. Historical material costs are explicitly marked as demo
    valuation entries and do not pretend to be real Stock Entry issues.
    """
    require_management()
    from wood_factory.setup import ensure_factory_roles

    ensure_factory_roles()
    company = _resolve_company(company)
    _validate_accounting_company(company)
    include_users = cint(include_users)
    include_stock = cint(include_stock)
    warnings = []

    frappe.db.savepoint("wood_factory_demo_data")
    try:
        context = _ensure_master_data(company, include_users=include_users)
        if include_stock:
            try:
                context["stock_receipt"] = _ensure_demo_stock(context)
            except Exception as exc:
                warnings.append(f"Stock receipt was skipped: {exc}")
                frappe.log_error(frappe.get_traceback(), "Wood Factory demo stock receipt")

        scenario_results = []
        for scenario in SCENARIOS:
            try:
                scenario_results.append(_ensure_scenario(context, scenario, warnings))
            except Exception as exc:
                warnings.append(f"{scenario.code}: {exc}")
                frappe.log_error(frappe.get_traceback(), f"Wood Factory demo scenario {scenario.code}")

        _ensure_demo_alerts(context, scenario_results)
        frappe.db.set_value("Factory Workstation", "DEMO Edge Bander 2", "status", "Maintenance", update_modified=False)
    except Exception:
        frappe.db.rollback(save_point="wood_factory_demo_data")
        raise

    result = _status(company)
    result.update({"created_or_refreshed": scenario_results, "warnings": warnings})
    return result


def _resolve_company(company=None):
    if company:
        if not frappe.db.exists("Company", company):
            frappe.throw(f"Company {company} does not exist")
        return company
    accounting_company = None
    if frappe.db.exists("DocType", "Factory Accounting Settings"):
        accounting_company = frappe.db.get_single_value("Factory Accounting Settings", "company")
    default_company = (
        accounting_company
        or frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if default_company and frappe.db.exists("Company", default_company):
        return default_company
    companies = frappe.get_all("Company", pluck="name", limit_page_length=1)
    if not companies:
        frappe.throw("Create an ERPNext Company before generating factory demo data")
    return companies[0]


def _validate_accounting_company(company):
    if not frappe.db.exists("DocType", "Factory Accounting Settings"):
        return
    settings = frappe.get_single("Factory Accounting Settings")
    if cint(settings.enabled) and settings.company and settings.company != company:
        frappe.throw(
            f"Factory Accounting Settings are enabled for {settings.company}. "
            f"Generate demo data for that company or change the settings first."
        )


def _ensure_master_data(company, include_users=True):
    company_values = frappe.db.get_value("Company", company, ["abbr", "default_currency", "cost_center"], as_dict=True) or frappe._dict()
    currency = company_values.default_currency or "USD"
    abbr = company_values.abbr or "DEMO"
    _ensure_uom("Nos")
    _ensure_uom("Meter")
    item_group = _ensure_item_group()
    customer_group = _ensure_customer_group()
    territory = _ensure_territory()
    price_list = _ensure_price_list(currency)
    warehouses = _ensure_warehouses(company, abbr)
    items = _ensure_items(item_group)
    customers = {scenario.customer: _ensure_customer(scenario.customer, customer_group, territory) for scenario in SCENARIOS}
    users = _ensure_users(company) if include_users else {key: "Administrator" for key in USER_DEFINITIONS}
    workstations = _ensure_workstations(company)
    return {
        "company": company,
        "currency": currency,
        "abbr": abbr,
        "default_cost_center": company_values.cost_center,
        "price_list": price_list,
        "warehouses": warehouses,
        "items": items,
        "customers": customers,
        "users": users,
        "workstations": workstations,
    }


def _ensure_uom(name):
    if frappe.db.exists("UOM", name):
        return name
    doc = frappe.new_doc("UOM")
    doc.uom_name = name
    if doc.meta.has_field("enabled"):
        doc.enabled = 1
    doc.insert(ignore_permissions=True)
    return doc.name


def _first_group(doctype, name_field):
    rows = frappe.get_all(doctype, filters={"is_group": 1}, fields=["name", name_field], order_by="lft asc", limit_page_length=1)
    if not rows:
        frappe.throw(f"No root {doctype} exists")
    return rows[0].name


def _ensure_item_group():
    name = "Factory Demo Items"
    existing = frappe.db.get_value("Item Group", {"item_group_name": name}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Item Group")
    doc.item_group_name = name
    doc.parent_item_group = _first_group("Item Group", "item_group_name")
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_customer_group():
    name = "Factory Demo Customers"
    existing = frappe.db.get_value("Customer Group", {"customer_group_name": name}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Customer Group")
    doc.customer_group_name = name
    doc.parent_customer_group = _first_group("Customer Group", "customer_group_name")
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_territory():
    name = "Factory Demo Territory"
    existing = frappe.db.get_value("Territory", {"territory_name": name}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Territory")
    doc.territory_name = name
    doc.parent_territory = _first_group("Territory", "territory_name")
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_price_list(currency):
    name = "Factory Demo Selling"
    if frappe.db.exists("Price List", name):
        return name
    doc = frappe.new_doc("Price List")
    doc.price_list_name = name
    doc.enabled = 1
    doc.selling = 1
    doc.buying = 0
    doc.currency = currency
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_warehouses(company, abbr):
    root_rows = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 1},
        fields=["name"],
        order_by="lft asc",
        limit_page_length=1,
    )
    if not root_rows:
        frappe.throw(f"No warehouse root exists for {company}")
    parent = _ensure_warehouse("WF Demo Factory", company, root_rows[0].name, is_group=1)
    definitions = {
        "boards": "WF Demo Raw Boards",
        "edge": "WF Demo Edge Band",
        "wip": "WF Demo Work In Progress",
        "finished": "WF Demo Finished Goods",
        "remnants": "WF Demo Remnants",
    }
    return {key: _ensure_warehouse(label, company, parent, is_group=0) for key, label in definitions.items()}


def _ensure_warehouse(label, company, parent, is_group=0):
    existing = frappe.db.get_value("Warehouse", {"warehouse_name": label, "company": company}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Warehouse")
    doc.warehouse_name = label
    doc.company = company
    doc.parent_warehouse = parent
    doc.is_group = is_group
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_items(item_group):
    definitions = {
        "white_board": (f"{DEMO_PREFIX}-MDF-WHITE-18", "Demo MDF White 18 mm", "Nos", 1, 42.0),
        "oak_board": (f"{DEMO_PREFIX}-MDF-OAK-18", "Demo MDF Oak 18 mm", "Nos", 1, 49.0),
        "white_edge": (f"{DEMO_PREFIX}-EDGE-WHITE-2", "Demo White Edge Band 2 cm", "Meter", 1, 0.65),
        "oak_edge": (f"{DEMO_PREFIX}-EDGE-OAK-2", "Demo Oak Edge Band 2 cm", "Meter", 1, 0.8),
        "custom_job": (f"{DEMO_PREFIX}-CUSTOM-JOB", "Demo Custom Kitchen / Wood Job", "Nos", 0, 0),
    }
    result = {}
    for key, (code, label, uom, stock, valuation) in definitions.items():
        if not frappe.db.exists("Item", code):
            doc = frappe.new_doc("Item")
            doc.item_code = code
            doc.item_name = label
            doc.item_group = item_group
            doc.stock_uom = uom
            doc.is_stock_item = stock
            if doc.meta.has_field("include_item_in_manufacturing"):
                doc.include_item_in_manufacturing = stock
            if doc.meta.has_field("valuation_rate"):
                doc.valuation_rate = valuation
            doc.description = f"{DEMO_TAG} Safe synthetic item for Wood Factory demonstrations"
            doc.insert(ignore_permissions=True)
        result[key] = code
    return result


def _ensure_customer(label, customer_group, territory):
    existing = frappe.db.get_value("Customer", {"customer_name": label}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Customer")
    doc.customer_name = label
    doc.customer_type = "Company"
    doc.customer_group = customer_group
    doc.territory = territory
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_users(company):
    result = {}
    for key, (email, full_name, role, hourly_cost) in USER_DEFINITIONS.items():
        if not frappe.db.exists("User", email):
            names = full_name.split(" ", 1)
            doc = frappe.new_doc("User")
            doc.email = email
            doc.first_name = names[0]
            doc.last_name = names[1] if len(names) > 1 else "Worker"
            doc.enabled = 0
            doc.user_type = "System User"
            doc.send_welcome_email = 0
            doc.append("roles", {"role": role})
            doc.insert(ignore_permissions=True)
        else:
            user = frappe.get_doc("User", email)
            if role not in {row.role for row in user.roles}:
                user.append("roles", {"role": role})
                user.save(ignore_permissions=True)
        result[key] = email
        _ensure_worker_rate(email, company, hourly_cost)
    return result


def _ensure_worker_rate(user, company, hourly_cost):
    existing = frappe.db.get_value(
        "Factory Worker Cost Rate",
        {"user": user, "company": company, "active": 1, "notes": ["like", f"%{DEMO_TAG}%"]},
        "name",
    )
    if existing:
        return existing
    doc = frappe.new_doc("Factory Worker Cost Rate")
    doc.user = user
    doc.company = company
    doc.hourly_cost = hourly_cost
    doc.effective_from = add_days(nowdate(), -365)
    doc.active = 1
    doc.notes = f"{DEMO_TAG} Synthetic worker rate"
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_workstations(company):
    result = {}
    for name, stage, status, minutes, efficiency, labor_rate, machine_rate, reason in WORKSTATION_DEFINITIONS:
        if frappe.db.exists("Factory Workstation", name):
            doc = frappe.get_doc("Factory Workstation", name)
        else:
            doc = frappe.new_doc("Factory Workstation")
            doc.workstation_name = name
        doc.stage = stage
        doc.company = company
        doc.status = status
        doc.minutes_per_day = minutes
        doc.efficiency_percent = efficiency
        doc.track_labor_cost = 1
        doc.default_labor_hourly_cost = labor_rate
        doc.track_machine_cost = 1 if machine_rate else 0
        doc.machine_hourly_cost = machine_rate
        doc.unavailable_reason = reason
        doc.notes = f"{DEMO_TAG} Synthetic workstation"
        doc.save(ignore_permissions=True) if not doc.is_new() else doc.insert(ignore_permissions=True)
        result.setdefault(stage, []).append(doc.name)
    return result


def _ensure_demo_stock(context):
    marker = f"{DEMO_TAG} MATERIAL RECEIPT {context['company']}"
    existing = frappe.db.get_value("Stock Entry", {"remarks": marker, "docstatus": 1}, "name")
    if existing:
        return existing
    receipt = frappe.new_doc("Stock Entry")
    receipt.stock_entry_type = "Material Receipt"
    receipt.company = context["company"]
    receipt.remarks = marker
    receipt.set_posting_time = 1
    receipt.posting_date = add_days(nowdate(), -30)
    receipt.posting_time = "08:00:00"
    stock_rows = (
        (context["items"]["white_board"], context["warehouses"]["boards"], 80, 42.0, "Nos"),
        (context["items"]["oak_board"], context["warehouses"]["boards"], 60, 49.0, "Nos"),
        (context["items"]["white_edge"], context["warehouses"]["edge"], 1500, 0.65, "Meter"),
        (context["items"]["oak_edge"], context["warehouses"]["edge"], 1200, 0.8, "Meter"),
    )
    for item_code, warehouse, qty, rate, uom in stock_rows:
        receipt.append("items", {
            "item_code": item_code,
            "t_warehouse": warehouse,
            "qty": qty,
            "basic_rate": rate,
            "uom": uom,
            "stock_uom": uom,
            "conversion_factor": 1,
        })
    receipt.insert(ignore_permissions=True)
    receipt.submit()
    return receipt.name


def _ensure_scenario(context, scenario, warnings):
    sales_order = _ensure_sales_order(context, scenario)
    order = _ensure_factory_order(context, scenario, sales_order)
    cutting = _ensure_cutting_order(context, scenario, order, warnings)
    _apply_stage_profile(context, scenario, order)
    _seed_material_cost(context, scenario, order, cutting)
    _seed_completed_stage_costs(context, order, warnings)
    exception = _ensure_exception(context, scenario, order, cutting, warnings) if scenario.exception_mode else None
    order.reload()
    if scenario.ready_for_delivery and order.status not in ("Ready for Delivery", "Delivered"):
        try:
            from wood_factory.delivery import mark_ready_for_delivery
            mark_ready_for_delivery(order.name)
        except Exception as exc:
            warnings.append(f"{scenario.code} delivery readiness: {exc}")
    if scenario.delivered and frappe.db.get_value("Factory Order", order.name, "status") != "Delivered":
        try:
            from wood_factory.delivery import confirm_delivered
            confirm_delivered(order.name)
        except Exception as exc:
            warnings.append(f"{scenario.code} delivery confirmation: {exc}")
    return {
        "scenario": scenario.code,
        "sales_order": sales_order,
        "factory_order": order.name,
        "cutting_order": cutting.name,
        "piece_exception": exception,
        "status": frappe.db.get_value("Factory Order", order.name, "status"),
    }


def _ensure_sales_order(context, scenario):
    marker = f"{DEMO_PREFIX}-{scenario.code}"
    existing = frappe.db.get_value("Sales Order", {"po_no": marker}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Sales Order")
    doc.customer = context["customers"][scenario.customer]
    doc.company = context["company"]
    doc.transaction_date = add_days(nowdate(), -max(scenario.history_days, 0))
    doc.delivery_date = add_days(nowdate(), scenario.delivery_offset)
    doc.order_type = "Sales"
    doc.currency = context["currency"]
    doc.conversion_rate = 1
    doc.selling_price_list = context["price_list"]
    doc.price_list_currency = context["currency"]
    doc.plc_conversion_rate = 1
    doc.po_no = marker
    doc.remarks = f"{DEMO_TAG} {scenario.description}"
    doc.append("items", {
        "item_code": context["items"]["custom_job"],
        "item_name": "Demo Custom Kitchen / Wood Job",
        "description": scenario.description,
        "qty": 1,
        "uom": "Nos",
        "stock_uom": "Nos",
        "conversion_factor": 1,
        "rate": scenario.revenue,
        "delivery_date": doc.delivery_date,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_factory_order(context, scenario, sales_order):
    existing = frappe.db.get_value("Factory Order", {"sales_order": sales_order}, "name")
    if existing:
        return frappe.get_doc("Factory Order", existing)
    doc = frappe.new_doc("Factory Order")
    doc.sales_order = sales_order
    doc.customer = context["customers"][scenario.customer]
    doc.company = context["company"]
    doc.currency = context["currency"]
    doc.order_date = add_days(nowdate(), -max(scenario.history_days, 0))
    doc.expected_delivery_date = add_days(nowdate(), scenario.delivery_offset)
    doc.status = "Confirmed"
    doc.cost_center = context.get("default_cost_center")
    doc.rework_cost_center = context.get("default_cost_center")
    doc.notes = f"{DEMO_TAG}<br>{scenario.description}"
    doc.insert(ignore_permissions=True)
    doc.initialize_production_stages()
    return frappe.get_doc("Factory Order", doc.name)


def _ensure_cutting_order(context, scenario, order, warnings):
    existing = frappe.db.get_value("Cutting Order", {"factory_order": order.name, "order_type": "Customer Order"}, "name")
    if existing:
        return frappe.get_doc("Cutting Order", existing)
    board_key = "white_board" if "WHITE" in scenario.board_item else "oak_board"
    edge_key = "white_edge" if board_key == "white_board" else "oak_edge"
    edge_rate = 0.65 if edge_key == "white_edge" else 0.8
    doc = frappe.new_doc("Cutting Order")
    doc.factory_order = order.name
    doc.order_type = "Customer Order"
    doc.customer_billable = 1
    doc.board_item = context["items"][board_key]
    doc.board_warehouse = context["warehouses"]["boards"]
    doc.edge_band_warehouse = context["warehouses"]["edge"]
    doc.board_width_mm = BOARD_WIDTH_MM
    doc.board_height_mm = BOARD_HEIGHT_MM
    doc.saw_kerf_mm = 3
    doc.algorithm = "Auto"
    doc.status = "Draft"
    for template in PART_TEMPLATES:
        top, right, bottom, left = template["edges"]
        doc.append("parts", {
            "part_name": template["part_name"],
            "width_mm": template["width_mm"],
            "height_mm": template["height_mm"],
            "qty": template["qty"],
            "allow_rotation": template["allow_rotation"],
            "grain_direction": template["grain_direction"],
            "edge_top": top,
            "edge_right": right,
            "edge_bottom": bottom,
            "edge_left": left,
            "edge_band_item": context["items"][edge_key],
            "edge_band_rate_per_m": edge_rate,
            "notes": f"{DEMO_TAG} {scenario.code}",
        })
    doc.insert(ignore_permissions=True)
    doc.optimize_layout()
    doc.reload()
    try:
        doc._create_factory_pieces()
    except Exception as exc:
        if "already exist" not in str(exc).lower():
            warnings.append(f"{scenario.code} pieces: {exc}")
    return frappe.get_doc("Cutting Order", doc.name)


def _stage_workstation(context, stage, alternate=False):
    rows = context["workstations"].get(stage) or []
    if not rows:
        return None
    return rows[1] if alternate and len(rows) > 1 else rows[0]


def _apply_stage_profile(context, scenario, order):
    order.reload()
    base = add_to_date(now_datetime(), days=-max(scenario.history_days, 1), hours=-2)
    durations = {"Cutting": 95, "Edge Banding": 70, "Drilling": 45, "Assembly": 110, "Quality Inspection": 28, "Packing": 38}
    cursor = base
    for index, row in enumerate(order.production_stages):
        row.workstation = _stage_workstation(context, row.stage)
        row.blocked_minutes = 0
        row.block_reason = None
        row.blocked_at = None
        row.internal_rework = 0
        if index < scenario.completed_stages:
            minutes = durations[row.stage] + (index * 3)
            row.status = "Completed"
            row.responsible = context["users"].get(row.stage, "Administrator")
            row.started_at = cursor
            row.completed_at = add_to_date(cursor, minutes=minutes)
            row.actual_minutes = minutes
            row.costing_status = row.costing_status or "Pending"
            cursor = add_to_date(row.completed_at, minutes=25)
        elif scenario.current_stage and row.stage == scenario.current_stage:
            row.status = scenario.stage_status or "Ready"
            row.responsible = context["users"].get(row.stage) if row.status in ("In Progress", "Blocked") else None
            if row.status in ("In Progress", "Blocked"):
                row.started_at = add_to_date(now_datetime(), hours=-3)
            if row.status == "Blocked":
                row.blocked_at = add_to_date(now_datetime(), hours=-10)
                row.block_reason = "Demo machine interruption waiting for maintenance"
            row.completed_at = None
            row.actual_minutes = 0
        else:
            row.status = "Pending"
            row.responsible = None
            row.started_at = None
            row.completed_at = None
            row.actual_minutes = 0
            row.workstation = None
    if scenario.completed_stages >= len(STAGES):
        order.status = "Quality Inspection"
    elif scenario.stage_status in ("In Progress", "Blocked"):
        order.status = "In Production"
    else:
        order.status = "Ready for Production"
    order.save(ignore_permissions=True)
    order._sync_normal_pieces()


def _fallback_context(context, internal_rework=False):
    return frappe._dict({
        "company": context["company"],
        "cost_center": context.get("default_cost_center"),
        "expense_account": None,
        "project": None,
        "currency": context["currency"],
        "cost_owner": "Factory Internal Rework" if internal_rework else "Demo Customer Order",
        "customer_billable": 0 if internal_rework else 1,
        "create_cost_ledger": 1,
    })


def _seed_material_cost(context, scenario, order, cutting):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    transaction_key = f"Demo|{scenario.code}|Customer Material"
    if frappe.db.exists("Factory Cost Ledger", {"transaction_key": transaction_key}):
        return
    board_rate = 42 if "WHITE" in scenario.board_item else 49
    amount = flt(cutting.board_count * board_rate + cutting.total_edge_band_length_m * (0.65 if "WHITE" in scenario.board_item else 0.8), 2)
    ledger = _create_cost_ledger(
        transaction_key=transaction_key,
        factory_order=order.name,
        cutting_order=cutting.name,
        transaction_type="Customer Material Consumption",
        context=_fallback_context(context, internal_rework=False),
        amount=amount,
        accounting_document_type="Cutting Order",
        accounting_document=cutting.name,
        remarks=f"{DEMO_TAG} Synthetic historical material valuation; no Material Issue Stock Entry is claimed",
    )
    cutting.db_set({
        "accounting_status": "Posted",
        "company": context["company"],
        "currency": context["currency"],
        "stock_entry_value": amount,
        "cost_ledger_entry": ledger.name,
        "cost_owner": f"Demo Customer Order {order.name}",
    })
    sync_factory_order_actual_costs(order.name)


def _seed_completed_stage_costs(context, order, warnings):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import get_worker_hourly_rate, get_workstation_costing, post_order_stage_cost, sync_factory_order_actual_costs

    order.reload()
    for row in order.production_stages:
        if row.status != "Completed":
            continue
        try:
            post_order_stage_cost(order, row.name)
            continue
        except Exception as exc:
            warnings.append(f"{order.name} {row.stage} costing fallback: {exc}")
        workstation = get_workstation_costing(row.workstation)
        labor_rate = get_worker_hourly_rate(row.responsible, context["company"], row.workstation, row.completed_at) if cint(workstation.get("track_labor_cost")) else 0
        machine_rate = flt(workstation.get("machine_hourly_cost")) if cint(workstation.get("track_machine_cost")) else 0
        labor = flt(row.actual_minutes / 60 * labor_rate, 2)
        machine = flt(row.actual_minutes / 60 * machine_rate, 2)
        fallback = _fallback_context(context, internal_rework=False)
        if labor > 0:
            _create_cost_ledger(
                transaction_key=f"Demo|{order.name}|{row.name}|Labor",
                factory_order=order.name,
                transaction_type="Labor Cost",
                context=fallback,
                amount=labor,
                factory_order_stage=row.name,
                production_stage=row.stage,
                workstation=row.workstation,
                responsible=row.responsible,
                actual_minutes=row.actual_minutes,
                hourly_rate=labor_rate,
                accounting_document_type="Factory Order",
                accounting_document=order.name,
                remarks=f"{DEMO_TAG} Historical demo labor cost",
            )
        if machine > 0:
            _create_cost_ledger(
                transaction_key=f"Demo|{order.name}|{row.name}|Machine",
                factory_order=order.name,
                transaction_type="Machine Cost",
                context=fallback,
                amount=machine,
                factory_order_stage=row.name,
                production_stage=row.stage,
                workstation=row.workstation,
                responsible=row.responsible,
                actual_minutes=row.actual_minutes,
                hourly_rate=machine_rate,
                accounting_document_type="Factory Order",
                accounting_document=order.name,
                remarks=f"{DEMO_TAG} Historical demo machine cost",
            )
        frappe.db.set_value("Factory Order Stage", row.name, {
            "labor_hourly_rate": labor_rate,
            "machine_hourly_rate": machine_rate,
            "labor_cost": labor,
            "machine_cost": machine,
            "costing_status": "Posted",
        }, update_modified=False)
    sync_factory_order_actual_costs(order.name)


def _pick_piece(order, prefer_large=False):
    fields = ["name", "piece_uid", "width_mm", "height_mm", "cutting_order", "board_layout"]
    pieces = frappe.get_all("Factory Piece", filters={"factory_order": order.name, "is_exception": 0}, fields=fields, limit_page_length=0)
    if not pieces:
        frappe.throw(f"No Factory Piece exists for {order.name}")
    pieces.sort(key=lambda row: flt(row.width_mm) * flt(row.height_mm), reverse=prefer_large)
    return pieces[0]


def _ensure_exception(context, scenario, order, cutting, warnings):
    existing = frappe.db.get_value("Piece Exception", {"factory_order": order.name, "reason": ["like", f"%{DEMO_TAG}%"]}, "name")
    if existing:
        return existing
    piece = _pick_piece(order, prefer_large=scenario.exception_mode == "new_board")
    exception = frappe.new_doc("Piece Exception")
    exception.factory_piece = piece.name
    exception.exception_type = "Damaged" if scenario.exception_mode == "remnant" else "Wrong Dimensions"
    exception.reason = f"{DEMO_TAG} {scenario.description}"
    exception.responsible = context["users"].get("supervisor", "Administrator")
    exception.insert(ignore_permissions=True)
    exception.require_replacement()
    exception.start_replacement()
    exception.reload()

    if scenario.exception_mode == "remnant":
        replacement = frappe.get_doc("Factory Piece", exception.replacement_piece)
        remnant = _ensure_available_remnant(context, scenario, cutting, replacement)
        try:
            exception.find_best_remnant()
        except Exception as exc:
            warnings.append(f"{scenario.code} remnant reservation: {exc}")
        return exception.name

    try:
        result = exception.create_replacement_cutting_order()
        replacement_cutting = frappe.get_doc("Cutting Order", result["cutting_order"])
        replacement_cutting.optimize_layout()
        replacement_cutting.reload()
        _seed_internal_replacement_cost(context, scenario, order, replacement_cutting, exception)
        _ensure_recovered_new_board_remnant(context, scenario, replacement_cutting, exception)
    except Exception as exc:
        warnings.append(f"{scenario.code} replacement cutting order: {exc}")
    return exception.name


def _ensure_available_remnant(context, scenario, cutting, replacement):
    marker = f"{DEMO_TAG} AVAILABLE REMNANT {scenario.code}"
    existing = frappe.db.get_value("Board Remnant", {"notes": marker}, "name")
    if existing:
        return existing
    width = flt(replacement.width_mm) + 80
    height = flt(replacement.height_mm) + 80
    area = width * height / 1_000_000
    rate = 18 if "WHITE" in scenario.board_item else 21
    doc = frappe.new_doc("Board Remnant")
    doc.board_item = cutting.board_item
    doc.warehouse = context["warehouses"]["remnants"]
    doc.width_mm = width
    doc.height_mm = height
    doc.valuation_rate_per_m2 = rate
    doc.estimated_value = flt(area * rate, 2)
    doc.currency = context["currency"]
    doc.status = "Available"
    doc.notes = marker
    doc.insert(ignore_permissions=True)
    frappe.db.set_value("Board Remnant", doc.name, {"source_cutting_order": cutting.name, "source_board_layout": piece_layout(replacement)}, update_modified=False)
    return doc.name


def piece_layout(piece):
    return piece.board_layout if getattr(piece, "board_layout", None) else None


def _seed_internal_replacement_cost(context, scenario, order, cutting, exception):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    key = f"Demo|{scenario.code}|Internal Replacement Material"
    if frappe.db.exists("Factory Cost Ledger", {"transaction_key": key}):
        return
    amount = 49 if "OAK" in scenario.board_item else 42
    ledger = _create_cost_ledger(
        transaction_key=key,
        factory_order=order.name,
        cutting_order=cutting.name,
        piece_exception=exception.name,
        transaction_type="Internal Replacement Material",
        context=_fallback_context(context, internal_rework=True),
        amount=amount,
        accounting_document_type="Cutting Order",
        accounting_document=cutting.name,
        remarks=f"{DEMO_TAG} Factory-funded replacement board valuation",
    )
    cutting.db_set({
        "accounting_status": "Posted",
        "company": context["company"],
        "currency": context["currency"],
        "stock_entry_value": amount,
        "cost_ledger_entry": ledger.name,
        "cost_owner": "Factory Internal Rework",
    })
    sync_factory_order_actual_costs(order.name)


def _ensure_recovered_new_board_remnant(context, scenario, cutting, exception):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    marker = f"{DEMO_TAG} RECOVERED NEW BOARD {scenario.code}"
    existing = frappe.db.get_value("Board Remnant", {"notes": marker}, "name")
    if existing:
        return existing
    width, height = 950, 1200
    area = width * height / 1_000_000
    rate = 16.5
    doc = frappe.new_doc("Board Remnant")
    doc.board_item = cutting.board_item
    doc.warehouse = context["warehouses"]["remnants"]
    doc.width_mm = width
    doc.height_mm = height
    doc.valuation_rate_per_m2 = rate
    doc.estimated_value = flt(area * rate, 2)
    doc.currency = context["currency"]
    doc.status = "Available"
    doc.notes = marker
    doc.insert(ignore_permissions=True)
    layouts = frappe.get_all("Board Layout", filters={"cutting_order": cutting.name}, pluck="name", limit_page_length=1)
    frappe.db.set_value("Board Remnant", doc.name, {
        "source_cutting_order": cutting.name,
        "source_board_layout": layouts[0] if layouts else None,
    }, update_modified=False)
    ledger = _create_cost_ledger(
        transaction_key=f"Demo|{scenario.code}|Remnant Recovery|{doc.name}",
        factory_order=cutting.factory_order,
        cutting_order=cutting.name,
        piece_exception=exception.name,
        transaction_type="Remnant Recovery",
        context=_fallback_context(context, internal_rework=True),
        amount=-abs(doc.estimated_value),
        accounting_document_type="Board Remnant",
        accounting_document=doc.name,
        remarks=f"{DEMO_TAG} Reusable remainder recovered from replacement board",
    )
    frappe.db.set_value("Board Remnant", doc.name, "recovery_cost_ledger", ledger.name, update_modified=False)
    sync_factory_order_actual_costs(cutting.factory_order)
    return doc.name


def _ensure_demo_alerts(context, scenario_results):
    references = {row["scenario"]: row for row in scenario_results}
    definitions = []
    delayed = references.get("DELAYED-BLOCKED")
    damaged = references.get("DAMAGED-REMNANT")
    if delayed:
        definitions.extend([
            (f"{DEMO_PREFIX}|Order Delay|{delayed['factory_order']}", "Order Delay", "Critical", "Escalated", "Factory Order", delayed["factory_order"], "Demo order is three days late", context["users"].get("planner"), context["users"].get("supervisor"), 3),
            (f"{DEMO_PREFIX}|Blocked Stage|{delayed['factory_order']}", "Blocked Production Stage", "High", "Open", "Factory Order", delayed["factory_order"], "Edge banding has remained blocked for more than eight hours", context["users"].get("Edge Banding"), context["users"].get("supervisor"), 2),
        ])
    if damaged and damaged.get("piece_exception"):
        definitions.append((
            f"{DEMO_PREFIX}|Piece Exception|{damaged['piece_exception']}", "Piece Exception", "High", "Acknowledged", "Piece Exception", damaged["piece_exception"], "Damaged piece replacement is waiting for cutting from a reserved remnant", context["users"].get("supervisor"), None, 1,
        ))
    definitions.append((
        f"{DEMO_PREFIX}|Workstation|DEMO Edge Bander 2", "Workstation Unavailable", "High", "Open", "Factory Workstation", "DEMO Edge Bander 2", "Second edge bander is under scheduled maintenance", context["users"].get("supervisor"), None, 1,
    ))
    for key, alert_type, severity, status, ref_type, ref_name, description, responsible, escalated_to, count in definitions:
        if frappe.db.exists("Factory Alert Log", {"alert_key": key}):
            continue
        now = now_datetime()
        doc = frappe.new_doc("Factory Alert Log")
        doc.update({
            "alert_key": key,
            "alert_type": alert_type,
            "severity": severity,
            "status": status,
            "reference_doctype": ref_type,
            "reference_name": ref_name,
            "description": f"{DEMO_TAG} {description}",
            "responsible": responsible,
            "escalated_to": escalated_to,
            "first_detected_at": add_to_date(now, hours=-12),
            "last_detected_at": now,
            "last_notified_at": add_to_date(now, hours=-1),
            "notification_count": count,
            "acknowledged_at": add_to_date(now, hours=-2) if status == "Acknowledged" else None,
            "acknowledged_by": responsible if status == "Acknowledged" else None,
            "escalated_at": add_to_date(now, hours=-4) if status == "Escalated" else None,
        })
        doc.insert(ignore_permissions=True)


def _status(company):
    scenarios = []
    for scenario in SCENARIOS:
        sales_order = frappe.db.get_value("Sales Order", {"po_no": f"{DEMO_PREFIX}-{scenario.code}"}, "name")
        factory_order = frappe.db.get_value("Factory Order", {"sales_order": sales_order}, "name") if sales_order else None
        scenarios.append({
            "code": scenario.code,
            "description": scenario.description,
            "sales_order": sales_order,
            "factory_order": factory_order,
            "status": frappe.db.get_value("Factory Order", factory_order, "status") if factory_order else "Missing",
        })
    return {
        "company": company,
        "ready": all(row["factory_order"] for row in scenarios),
        "counts": {
            "items": frappe.db.count("Item", {"item_code": ["like", f"{DEMO_PREFIX}-%"]}),
            "customers": frappe.db.count("Customer", {"customer_name": ["like", "DEMO - %"]}),
            "workstations": frappe.db.count("Factory Workstation", {"name": ["like", "DEMO %"]}),
            "users": frappe.db.count("User", {"name": ["like", "wf.demo.%@example.com"]}),
            "factory_orders": sum(1 for row in scenarios if row["factory_order"]),
            "piece_exceptions": frappe.db.count("Piece Exception", {"reason": ["like", f"%{DEMO_TAG}%"]}),
            "remnants": frappe.db.count("Board Remnant", {"notes": ["like", f"%{DEMO_TAG}%"]}),
            "alerts": frappe.db.count("Factory Alert Log", {"alert_key": ["like", f"{DEMO_PREFIX}|%"]}),
        },
        "scenarios": scenarios,
        "notes": [
            "Demo users are disabled and no welcome emails are sent.",
            "Demo generation is idempotent and does not delete production data.",
            "Synthetic material valuation ledger entries are clearly marked and are not claimed as Stock Entry issues.",
        ],
    }
