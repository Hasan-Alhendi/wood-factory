from __future__ import annotations

import re

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
BOARD_WIDTH_MM = 1220
BOARD_HEIGHT_MM = 2440
STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")

SCENARIOS = (
    {
        "code": "NORMAL-CUTTING",
        "customer": "Al Noor Kitchens",
        "revenue": 1850,
        "delivery_offset": 5,
        "board": "white_board",
        "current_stage": "Cutting",
        "stage_status": "Ready",
        "completed_stages": 0,
        "history_days": 0,
        "description": "Normal customer order waiting for cutting.",
    },
    {
        "code": "DELAYED-BLOCKED",
        "customer": "Al Madina Showroom",
        "revenue": 2750,
        "delivery_offset": -3,
        "board": "oak_board",
        "current_stage": "Edge Banding",
        "stage_status": "Blocked",
        "completed_stages": 1,
        "history_days": 4,
        "description": "Late order blocked in edge banding because a machine is unavailable.",
    },
    {
        "code": "DAMAGED-REMNANT",
        "customer": "Horizon Interiors",
        "revenue": 1450,
        "delivery_offset": 2,
        "board": "white_board",
        "current_stage": "Quality Inspection",
        "stage_status": "Ready",
        "completed_stages": 4,
        "history_days": 6,
        "description": "Damaged piece found at quality inspection; replacement uses a matching remnant.",
        "exception_mode": "remnant",
    },
    {
        "code": "WRONG-DIM-NEW-BOARD",
        "customer": "Damascus Decor",
        "revenue": 3200,
        "delivery_offset": 1,
        "board": "oak_board",
        "current_stage": "Assembly",
        "stage_status": "In Progress",
        "completed_stages": 3,
        "history_days": 5,
        "description": "Wrong-dimension piece requires a factory-funded replacement from a new board.",
        "exception_mode": "new_board",
    },
    {
        "code": "READY-DELIVERY",
        "customer": "Modern Kitchen Center",
        "revenue": 2100,
        "delivery_offset": 0,
        "board": "white_board",
        "current_stage": None,
        "stage_status": None,
        "completed_stages": 6,
        "history_days": 10,
        "description": "Completed order waiting for delivery confirmation.",
        "ready_for_delivery": True,
    },
    {
        "code": "DELIVERED",
        "customer": "Elegant Woodworks",
        "revenue": 2400,
        "delivery_offset": -7,
        "board": "oak_board",
        "current_stage": None,
        "stage_status": None,
        "completed_stages": 6,
        "history_days": 18,
        "description": "Historically completed and delivered order used by profitability reports.",
        "ready_for_delivery": True,
        "delivered": True,
    },
)

ROLE_USERS = {
    "supervisor": ("Demo Factory Supervisor", FACTORY_SUPERVISOR, 6.5),
    "planner": ("Demo Factory Planner", FACTORY_PLANNER, 6.0),
    "accountant": ("Demo Factory Accountant", FACTORY_ACCOUNTANT, 6.0),
    "Cutting": ("Demo Cutting Worker", FACTORY_CUTTING_OPERATOR, 4.5),
    "Edge Banding": ("Demo Edge Banding Worker", FACTORY_EDGE_OPERATOR, 4.2),
    "Drilling": ("Demo Drilling Worker", FACTORY_DRILLING_OPERATOR, 4.4),
    "Assembly": ("Demo Assembly Worker", FACTORY_ASSEMBLY_OPERATOR, 4.0),
    "Quality Inspection": ("Demo Quality Inspector", FACTORY_QUALITY_INSPECTOR, 5.0),
    "Packing": ("Demo Packing Worker", FACTORY_PACKING_OPERATOR, 3.8),
    "delivery": ("Demo Delivery User", FACTORY_DELIVERY_USER, 3.8),
}

WORKSTATIONS = (
    ("Panel Saw 1", "Cutting", "Active", 480, 92, 4.5, 8.0, None),
    ("Panel Saw 2", "Cutting", "Active", 420, 85, 4.5, 6.5, None),
    ("Edge Bander 1", "Edge Banding", "Active", 450, 90, 4.2, 7.0, None),
    ("Edge Bander 2", "Edge Banding", "Maintenance", 450, 90, 4.2, 7.0, "Scheduled maintenance for demo bottleneck"),
    ("CNC Drill", "Drilling", "Active", 420, 88, 4.4, 9.0, None),
    ("Assembly Bench", "Assembly", "Active", 480, 82, 4.0, 2.0, None),
    ("Quality Station", "Quality Inspection", "Active", 480, 95, 5.0, 0.0, None),
    ("Packing Line", "Packing", "Active", 480, 90, 3.8, 1.5, None),
)

PARTS = (
    ("Tall Door", 450, 2100, 2, 0, "Along Height", (1, 1, 1, 1)),
    ("Wall Cabinet Door", 600, 720, 4, 1, "Any", (1, 1, 1, 1)),
    ("Drawer Front", 720, 220, 3, 1, "Any", (1, 1, 1, 1)),
    ("Side Panel", 560, 720, 2, 1, "Along Height", (1, 0, 1, 0)),
)


@frappe.whitelist()
def get_demo_status(company=None):
    require_management()
    context = _company_context(_resolve_company(company))
    return _status(context)


@frappe.whitelist()
def create_demo_dataset(company=None, include_users=1, include_stock=1):
    """Create safe, idempotent demo records without deleting production data."""
    require_management()
    from wood_factory.setup import ensure_factory_roles

    ensure_factory_roles()
    context = _company_context(_resolve_company(company))
    _validate_accounting_company(context["company"])
    warnings = []

    frappe.db.savepoint("wood_factory_demo_data")
    try:
        _ensure_master_data(context, include_users=cint(include_users))
        if cint(include_stock):
            try:
                context["stock_receipt"] = _ensure_stock_receipt(context)
            except Exception as exc:
                warnings.append(f"Demo stock receipt was skipped: {exc}")
                frappe.log_error(frappe.get_traceback(), "Wood Factory demo stock receipt")

        results = []
        for scenario in SCENARIOS:
            try:
                results.append(_ensure_scenario(context, scenario, warnings))
            except Exception as exc:
                warnings.append(f"{scenario['code']}: {exc}")
                frappe.log_error(frappe.get_traceback(), f"Wood Factory demo scenario {scenario['code']}")

        _ensure_alerts(context, results)
    except Exception:
        frappe.db.rollback(save_point="wood_factory_demo_data")
        raise

    output = _status(context)
    output.update({"created_or_refreshed": results, "warnings": warnings})
    return output


def _resolve_company(company=None):
    if company:
        if not frappe.db.exists("Company", company):
            frappe.throw(f"Company {company} does not exist")
        return company
    configured = None
    if frappe.db.exists("DocType", "Factory Accounting Settings"):
        configured = frappe.db.get_single_value("Factory Accounting Settings", "company")
    company = configured or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    if company and frappe.db.exists("Company", company):
        return company
    companies = frappe.get_all("Company", pluck="name", limit_page_length=1)
    if not companies:
        frappe.throw("Create an ERPNext Company before generating Wood Factory demo data")
    return companies[0]


def _company_context(company):
    values = frappe.db.get_value("Company", company, ["abbr", "default_currency", "cost_center"], as_dict=True) or frappe._dict()
    abbr = re.sub(r"[^A-Za-z0-9]", "", values.abbr or "DEMO").upper()
    return {
        "company": company,
        "abbr": abbr,
        "prefix": f"WF-DEMO-{abbr}",
        "currency": values.default_currency or "USD",
        "default_cost_center": values.cost_center,
    }


def _validate_accounting_company(company):
    if not frappe.db.exists("DocType", "Factory Accounting Settings"):
        return
    settings = frappe.get_single("Factory Accounting Settings")
    if cint(settings.enabled) and settings.company and settings.company != company:
        frappe.throw(
            f"Factory Accounting Settings are enabled for {settings.company}. "
            f"Generate demo data for that company or change the settings first."
        )


def _ensure_master_data(context, include_users=True):
    _ensure_uom("Nos")
    _ensure_uom("Meter")
    context["item_group"] = _ensure_leaf_group("Item Group", "Factory Demo Items", "item_group_name", "parent_item_group")
    context["customer_group"] = _ensure_leaf_group("Customer Group", "Factory Demo Customers", "customer_group_name", "parent_customer_group")
    context["territory"] = _ensure_leaf_group("Territory", "Factory Demo Territory", "territory_name", "parent_territory")
    context["price_list"] = _ensure_price_list(context)
    context["warehouses"] = _ensure_warehouses(context)
    context["items"] = _ensure_items(context)
    context["customers"] = {
        scenario["customer"]: _ensure_customer(context, scenario["customer"])
        for scenario in SCENARIOS
    }
    context["users"] = _ensure_users(context) if include_users else {key: "Administrator" for key in ROLE_USERS}
    context["workstations"] = _ensure_workstations(context)


def _ensure_uom(name):
    if frappe.db.exists("UOM", name):
        return name
    doc = frappe.new_doc("UOM")
    doc.uom_name = name
    if doc.meta.has_field("enabled"):
        doc.enabled = 1
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_leaf_group(doctype, label, name_field, parent_field):
    existing = frappe.db.get_value(doctype, {name_field: label}, "name")
    if existing:
        return existing
    roots = frappe.get_all(doctype, filters={"is_group": 1}, fields=["name"], order_by="lft asc", limit_page_length=1)
    if not roots:
        frappe.throw(f"No root {doctype} exists")
    doc = frappe.new_doc(doctype)
    doc.set(name_field, label)
    doc.set(parent_field, roots[0].name)
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_price_list(context):
    name = f"Factory Demo Selling {context['abbr']}"
    if frappe.db.exists("Price List", name):
        return name
    doc = frappe.new_doc("Price List")
    doc.price_list_name = name
    doc.enabled = 1
    doc.selling = 1
    doc.buying = 0
    doc.currency = context["currency"]
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_warehouses(context):
    roots = frappe.get_all(
        "Warehouse",
        filters={"company": context["company"], "is_group": 1},
        fields=["name"],
        order_by="lft asc",
        limit_page_length=1,
    )
    if not roots:
        frappe.throw(f"No Warehouse root exists for {context['company']}")
    parent = _ensure_warehouse(context, "WF Demo Factory", roots[0].name, is_group=1)
    return {
        "boards": _ensure_warehouse(context, "WF Demo Raw Boards", parent),
        "edge": _ensure_warehouse(context, "WF Demo Edge Band", parent),
        "wip": _ensure_warehouse(context, "WF Demo Work In Progress", parent),
        "finished": _ensure_warehouse(context, "WF Demo Finished Goods", parent),
        "remnants": _ensure_warehouse(context, "WF Demo Remnants", parent),
    }


def _ensure_warehouse(context, label, parent, is_group=0):
    existing = frappe.db.get_value("Warehouse", {"warehouse_name": label, "company": context["company"]}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Warehouse")
    doc.warehouse_name = label
    doc.company = context["company"]
    doc.parent_warehouse = parent
    doc.is_group = is_group
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_items(context):
    definitions = {
        "white_board": ("MDF-WHITE-18", "Demo MDF White 18 mm", "Nos", 1, 42.0),
        "oak_board": ("MDF-OAK-18", "Demo MDF Oak 18 mm", "Nos", 1, 49.0),
        "white_edge": ("EDGE-WHITE-2", "Demo White Edge Band 2 cm", "Meter", 1, 0.65),
        "oak_edge": ("EDGE-OAK-2", "Demo Oak Edge Band 2 cm", "Meter", 1, 0.80),
        "custom_job": ("CUSTOM-JOB", "Demo Custom Kitchen / Wood Job", "Nos", 0, 0),
    }
    result = {}
    for key, (suffix, label, uom, is_stock, valuation_rate) in definitions.items():
        code = f"{context['prefix']}-{suffix}"
        if not frappe.db.exists("Item", code):
            doc = frappe.new_doc("Item")
            doc.item_code = code
            doc.item_name = label
            doc.item_group = context["item_group"]
            doc.stock_uom = uom
            doc.is_stock_item = is_stock
            if doc.meta.has_field("include_item_in_manufacturing"):
                doc.include_item_in_manufacturing = is_stock
            if doc.meta.has_field("valuation_rate"):
                doc.valuation_rate = valuation_rate
            doc.description = f"{DEMO_TAG} Synthetic item for {context['company']}"
            doc.insert(ignore_permissions=True)
        result[key] = code
    return result


def _ensure_customer(context, label):
    customer_name = f"DEMO {context['abbr']} - {label}"
    existing = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Customer")
    doc.customer_name = customer_name
    doc.customer_type = "Company"
    doc.customer_group = context["customer_group"]
    doc.territory = context["territory"]
    doc.insert(ignore_permissions=True)
    return doc.name


def _demo_email(context, key):
    safe = re.sub(r"[^a-z0-9]+", ".", key.lower()).strip(".")
    return f"wf.demo.{context['abbr'].lower()}.{safe}@example.com"


def _ensure_users(context):
    users = {}
    for key, (full_name, role, hourly_cost) in ROLE_USERS.items():
        email = _demo_email(context, key)
        if not frappe.db.exists("User", email):
            parts = full_name.split(" ", 1)
            doc = frappe.new_doc("User")
            doc.email = email
            doc.first_name = parts[0]
            doc.last_name = parts[1] if len(parts) > 1 else "Worker"
            doc.enabled = 0
            doc.user_type = "System User"
            doc.send_welcome_email = 0
            doc.append("roles", {"role": role})
            doc.insert(ignore_permissions=True)
        else:
            doc = frappe.get_doc("User", email)
            if role not in {row.role for row in doc.roles}:
                doc.append("roles", {"role": role})
                doc.save(ignore_permissions=True)
        users[key] = email
        _ensure_worker_rate(context, email, hourly_cost)
    return users


def _ensure_worker_rate(context, user, hourly_cost):
    existing = frappe.db.get_value(
        "Factory Worker Cost Rate",
        {"user": user, "company": context["company"], "active": 1, "notes": ["like", f"%{DEMO_TAG}%"]},
        "name",
    )
    if existing:
        return existing
    doc = frappe.new_doc("Factory Worker Cost Rate")
    doc.user = user
    doc.company = context["company"]
    doc.hourly_cost = hourly_cost
    doc.effective_from = add_days(nowdate(), -365)
    doc.active = 1
    doc.notes = f"{DEMO_TAG} Synthetic worker rate"
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_workstations(context):
    by_stage = {}
    maintenance = None
    for label, stage, status, minutes, efficiency, labor_rate, machine_rate, reason in WORKSTATIONS:
        name = f"DEMO {context['abbr']} {label}"
        if frappe.db.exists("Factory Workstation", name):
            doc = frappe.get_doc("Factory Workstation", name)
        else:
            doc = frappe.new_doc("Factory Workstation")
            doc.workstation_name = name
        doc.stage = stage
        doc.company = context["company"]
        doc.status = status
        doc.minutes_per_day = minutes
        doc.efficiency_percent = efficiency
        doc.track_labor_cost = 1
        doc.default_labor_hourly_cost = labor_rate
        doc.track_machine_cost = 1 if machine_rate else 0
        doc.machine_hourly_cost = machine_rate
        doc.unavailable_reason = reason
        doc.notes = f"{DEMO_TAG} Synthetic workstation"
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
        by_stage.setdefault(stage, []).append(doc.name)
        if status != "Active":
            maintenance = doc.name
    context["maintenance_workstation"] = maintenance
    return by_stage


def _ensure_stock_receipt(context):
    marker = f"{DEMO_TAG} MATERIAL RECEIPT {context['company']}"
    submitted = frappe.db.get_value("Stock Entry", {"remarks": marker, "docstatus": 1}, "name")
    if submitted:
        return submitted
    drafts = frappe.get_all("Stock Entry", filters={"remarks": marker, "docstatus": 0}, pluck="name", limit_page_length=0)
    for name in drafts:
        frappe.delete_doc("Stock Entry", name, ignore_permissions=True, force=True)

    receipt = frappe.new_doc("Stock Entry")
    receipt.stock_entry_type = "Material Receipt"
    receipt.company = context["company"]
    receipt.remarks = marker
    receipt.set_posting_time = 1
    receipt.posting_date = add_days(nowdate(), -30)
    receipt.posting_time = "08:00:00"
    rows = (
        (context["items"]["white_board"], context["warehouses"]["boards"], 80, 42.0, "Nos"),
        (context["items"]["oak_board"], context["warehouses"]["boards"], 60, 49.0, "Nos"),
        (context["items"]["white_edge"], context["warehouses"]["edge"], 1500, 0.65, "Meter"),
        (context["items"]["oak_edge"], context["warehouses"]["edge"], 1200, 0.80, "Meter"),
    )
    for item_code, warehouse, qty, rate, uom in rows:
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
    _seed_customer_material_cost(context, scenario, order, cutting)
    _seed_completed_stage_costs(context, order)
    exception = _ensure_exception(context, scenario, order, cutting, warnings) if scenario.get("exception_mode") else None

    order.reload()
    if scenario.get("ready_for_delivery") and order.status not in ("Ready for Delivery", "Delivered"):
        try:
            from wood_factory.delivery import mark_ready_for_delivery
            mark_ready_for_delivery(order.name)
        except Exception as exc:
            warnings.append(f"{scenario['code']} delivery readiness: {exc}")
    if scenario.get("delivered") and frappe.db.get_value("Factory Order", order.name, "status") != "Delivered":
        try:
            from wood_factory.delivery import mark_delivered
            mark_delivered(order.name)
        except Exception as exc:
            warnings.append(f"{scenario['code']} delivery confirmation: {exc}")

    return {
        "scenario": scenario["code"],
        "sales_order": sales_order,
        "factory_order": order.name,
        "cutting_order": cutting.name,
        "piece_exception": exception,
        "status": frappe.db.get_value("Factory Order", order.name, "status"),
    }


def _sales_marker(context, scenario):
    return f"{context['prefix']}-{scenario['code']}"


def _ensure_sales_order(context, scenario):
    marker = _sales_marker(context, scenario)
    existing = frappe.db.get_value("Sales Order", {"po_no": marker, "company": context["company"]}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Sales Order")
    doc.customer = context["customers"][scenario["customer"]]
    doc.company = context["company"]
    doc.transaction_date = add_days(nowdate(), -max(scenario["history_days"], 0))
    doc.delivery_date = add_days(nowdate(), scenario["delivery_offset"])
    doc.order_type = "Sales"
    doc.currency = context["currency"]
    doc.conversion_rate = 1
    doc.selling_price_list = context["price_list"]
    doc.price_list_currency = context["currency"]
    doc.plc_conversion_rate = 1
    doc.po_no = marker
    doc.remarks = f"{DEMO_TAG} {scenario['description']}"
    doc.append("items", {
        "item_code": context["items"]["custom_job"],
        "item_name": "Demo Custom Kitchen / Wood Job",
        "description": scenario["description"],
        "qty": 1,
        "uom": "Nos",
        "stock_uom": "Nos",
        "conversion_factor": 1,
        "rate": scenario["revenue"],
        "delivery_date": doc.delivery_date,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_factory_order(context, scenario, sales_order):
    existing = frappe.db.get_value("Factory Order", {"sales_order": sales_order}, "name")
    if existing:
        doc = frappe.get_doc("Factory Order", existing)
        if not doc.production_stages:
            doc.initialize_production_stages()
        return frappe.get_doc("Factory Order", existing)
    doc = frappe.new_doc("Factory Order")
    doc.sales_order = sales_order
    doc.customer = context["customers"][scenario["customer"]]
    doc.company = context["company"]
    doc.currency = context["currency"]
    doc.order_date = add_days(nowdate(), -max(scenario["history_days"], 0))
    doc.expected_delivery_date = add_days(nowdate(), scenario["delivery_offset"])
    doc.status = "Confirmed"
    doc.cost_center = context.get("default_cost_center")
    doc.rework_cost_center = context.get("default_cost_center")
    doc.notes = f"{DEMO_TAG}<br>{scenario['description']}"
    doc.insert(ignore_permissions=True)
    doc.initialize_production_stages()
    return frappe.get_doc("Factory Order", doc.name)


def _ensure_cutting_order(context, scenario, order, warnings):
    existing = frappe.db.get_value("Cutting Order", {"factory_order": order.name, "order_type": "Customer Order"}, "name")
    if existing:
        doc = frappe.get_doc("Cutting Order", existing)
        if not frappe.db.exists("Board Layout", {"cutting_order": doc.name}):
            doc.optimize_layout()
            doc.reload()
        if not frappe.db.exists("Factory Piece", {"cutting_order": doc.name}):
            try:
                doc._create_factory_pieces()
            except Exception as exc:
                warnings.append(f"{scenario['code']} pieces: {exc}")
        return frappe.get_doc("Cutting Order", doc.name)

    board_key = scenario["board"]
    edge_key = "white_edge" if board_key == "white_board" else "oak_edge"
    edge_rate = 0.65 if edge_key == "white_edge" else 0.80
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
    for part_name, width, height, qty, rotate, grain, edges in PARTS:
        top, right, bottom, left = edges
        doc.append("parts", {
            "part_name": part_name,
            "width_mm": width,
            "height_mm": height,
            "qty": qty,
            "allow_rotation": rotate,
            "grain_direction": grain,
            "edge_top": top,
            "edge_right": right,
            "edge_bottom": bottom,
            "edge_left": left,
            "edge_band_item": context["items"][edge_key],
            "edge_band_rate_per_m": edge_rate,
            "notes": f"{DEMO_TAG} {scenario['code']}",
        })
    doc.insert(ignore_permissions=True)
    doc.optimize_layout()
    doc.reload()
    doc._create_factory_pieces()
    return frappe.get_doc("Cutting Order", doc.name)


def _active_workstation(context, stage):
    for name in context["workstations"].get(stage, []):
        if frappe.db.get_value("Factory Workstation", name, "status") == "Active":
            return name
    return None


def _apply_stage_profile(context, scenario, order):
    order.reload()
    durations = {"Cutting": 95, "Edge Banding": 70, "Drilling": 45, "Assembly": 110, "Quality Inspection": 28, "Packing": 38}
    cursor = add_to_date(now_datetime(), days=-max(scenario["history_days"], 1), hours=-2)
    for index, row in enumerate(order.production_stages):
        row.blocked_minutes = 0
        row.block_reason = None
        row.blocked_at = None
        row.internal_rework = 0
        if index < scenario["completed_stages"]:
            minutes = durations[row.stage] + index * 3
            row.status = "Completed"
            row.workstation = _active_workstation(context, row.stage)
            row.responsible = context["users"].get(row.stage, "Administrator")
            row.started_at = cursor
            row.completed_at = add_to_date(cursor, minutes=minutes)
            row.actual_minutes = minutes
            cursor = add_to_date(row.completed_at, minutes=25)
        elif scenario.get("current_stage") == row.stage:
            row.status = scenario.get("stage_status") or "Ready"
            row.workstation = _active_workstation(context, row.stage)
            row.responsible = context["users"].get(row.stage) if row.status in ("In Progress", "Blocked") else None
            row.started_at = add_to_date(now_datetime(), hours=-3) if row.status in ("In Progress", "Blocked") else None
            row.completed_at = None
            row.actual_minutes = 0
            if row.status == "Blocked":
                row.blocked_at = add_to_date(now_datetime(), hours=-10)
                row.block_reason = "Demo machine interruption waiting for maintenance"
        else:
            row.status = "Pending"
            row.workstation = None
            row.responsible = None
            row.started_at = None
            row.completed_at = None
            row.actual_minutes = 0
    if scenario["completed_stages"] >= len(STAGES):
        order.status = "Quality Inspection"
    elif scenario.get("stage_status") in ("In Progress", "Blocked"):
        order.status = "In Production"
    else:
        order.status = "Ready for Production"
    order.save(ignore_permissions=True)
    order._sync_normal_pieces()


def _ledger_context(context, internal=False):
    return frappe._dict({
        "company": context["company"],
        "cost_center": context.get("default_cost_center"),
        "expense_account": None,
        "project": None,
        "currency": context["currency"],
        "cost_owner": "Factory Internal Rework" if internal else "Demo Customer Order",
        "customer_billable": 0 if internal else 1,
        "create_cost_ledger": 1,
    })


def _seed_customer_material_cost(context, scenario, order, cutting):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    key = f"Demo|{order.name}|Customer Material"
    if frappe.db.exists("Factory Cost Ledger", {"transaction_key": key}):
        return
    board_rate = 42 if scenario["board"] == "white_board" else 49
    edge_rate = 0.65 if scenario["board"] == "white_board" else 0.80
    amount = flt(cutting.board_count * board_rate + cutting.total_edge_band_length_m * edge_rate, 2)
    ledger = _create_cost_ledger(
        transaction_key=key,
        factory_order=order.name,
        cutting_order=cutting.name,
        transaction_type="Customer Material Consumption",
        context=_ledger_context(context),
        amount=amount,
        accounting_document_type="Cutting Order",
        accounting_document=cutting.name,
        remarks=f"{DEMO_TAG} Synthetic historical material valuation; no Material Issue is claimed",
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


def _seed_completed_stage_costs(context, order):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import get_worker_hourly_rate, get_workstation_costing, sync_factory_order_actual_costs

    order.reload()
    for row in order.production_stages:
        if row.status != "Completed":
            continue
        workstation = get_workstation_costing(row.workstation)
        labor_rate = get_worker_hourly_rate(row.responsible, context["company"], row.workstation, row.completed_at) if cint(workstation.get("track_labor_cost")) else 0
        machine_rate = flt(workstation.get("machine_hourly_cost")) if cint(workstation.get("track_machine_cost")) else 0
        labor = flt(row.actual_minutes / 60 * labor_rate, 2)
        machine = flt(row.actual_minutes / 60 * machine_rate, 2)
        if labor > 0:
            _create_cost_ledger(
                transaction_key=f"Demo|{order.name}|{row.name}|Labor",
                factory_order=order.name,
                transaction_type="Labor Cost",
                context=_ledger_context(context),
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
                context=_ledger_context(context),
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


def _pick_piece(order, largest=False):
    pieces = frappe.get_all(
        "Factory Piece",
        filters={"factory_order": order.name, "is_exception": 0},
        fields=["name", "piece_uid", "width_mm", "height_mm", "cutting_order", "board_layout"],
        limit_page_length=0,
    )
    if not pieces:
        frappe.throw(f"No Factory Piece exists for {order.name}")
    pieces.sort(key=lambda row: flt(row.width_mm) * flt(row.height_mm), reverse=largest)
    return pieces[0]


def _ensure_exception(context, scenario, order, cutting, warnings):
    existing = frappe.db.get_value("Piece Exception", {"factory_order": order.name, "reason": ["like", f"%{DEMO_TAG}%"]}, "name")
    if existing:
        return existing
    piece = _pick_piece(order, largest=scenario["exception_mode"] == "new_board")
    doc = frappe.new_doc("Piece Exception")
    doc.factory_piece = piece.name
    doc.exception_type = "Damaged" if scenario["exception_mode"] == "remnant" else "Wrong Dimensions"
    doc.reason = f"{DEMO_TAG} {scenario['description']}"
    doc.responsible = context["users"].get("supervisor", "Administrator")
    doc.insert(ignore_permissions=True)
    doc.require_replacement()
    doc.start_replacement()
    doc.reload()

    if scenario["exception_mode"] == "remnant":
        replacement = frappe.get_doc("Factory Piece", doc.replacement_piece)
        _ensure_available_remnant(context, scenario, cutting, replacement)
        try:
            doc.find_best_remnant()
        except Exception as exc:
            warnings.append(f"{scenario['code']} remnant reservation: {exc}")
        return doc.name

    try:
        result = doc.create_replacement_cutting_order()
        replacement_cutting = frappe.get_doc("Cutting Order", result["cutting_order"])
        replacement_cutting.optimize_layout()
        replacement_cutting.reload()
        _seed_internal_replacement_cost(context, order, replacement_cutting, doc)
        _ensure_recovered_remnant(context, scenario, replacement_cutting, doc)
    except Exception as exc:
        warnings.append(f"{scenario['code']} replacement cutting order: {exc}")
    return doc.name


def _ensure_available_remnant(context, scenario, cutting, replacement):
    marker = f"{DEMO_TAG} AVAILABLE REMNANT {context['abbr']} {scenario['code']}"
    existing = frappe.db.get_value("Board Remnant", {"notes": marker}, "name")
    if existing:
        return existing
    width = flt(replacement.width_mm) + 80
    height = flt(replacement.height_mm) + 80
    rate = 18 if scenario["board"] == "white_board" else 21
    doc = frappe.new_doc("Board Remnant")
    doc.board_item = cutting.board_item
    doc.warehouse = context["warehouses"]["remnants"]
    doc.width_mm = width
    doc.height_mm = height
    doc.valuation_rate_per_m2 = rate
    doc.estimated_value = flt(width * height / 1_000_000 * rate, 2)
    doc.currency = context["currency"]
    doc.status = "Available"
    doc.notes = marker
    doc.insert(ignore_permissions=True)
    return doc.name


def _seed_internal_replacement_cost(context, order, cutting, exception):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    key = f"Demo|{cutting.name}|Internal Replacement Material"
    if frappe.db.exists("Factory Cost Ledger", {"transaction_key": key}):
        return
    amount = 49 if "OAK" in cutting.board_item else 42
    ledger = _create_cost_ledger(
        transaction_key=key,
        factory_order=order.name,
        cutting_order=cutting.name,
        piece_exception=exception.name,
        transaction_type="Internal Replacement Material",
        context=_ledger_context(context, internal=True),
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


def _ensure_recovered_remnant(context, scenario, cutting, exception):
    from wood_factory.accounting import _create_cost_ledger
    from wood_factory.costing import sync_factory_order_actual_costs

    marker = f"{DEMO_TAG} RECOVERED NEW BOARD {context['abbr']} {scenario['code']}"
    existing = frappe.db.get_value("Board Remnant", {"notes": marker}, "name")
    if existing:
        return existing
    doc = frappe.new_doc("Board Remnant")
    doc.board_item = cutting.board_item
    doc.warehouse = context["warehouses"]["remnants"]
    doc.width_mm = 950
    doc.height_mm = 1200
    doc.valuation_rate_per_m2 = 16.5
    doc.estimated_value = flt(950 * 1200 / 1_000_000 * 16.5, 2)
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
        transaction_key=f"Demo|{cutting.name}|Remnant Recovery|{doc.name}",
        factory_order=cutting.factory_order,
        cutting_order=cutting.name,
        piece_exception=exception.name,
        transaction_type="Remnant Recovery",
        context=_ledger_context(context, internal=True),
        amount=-abs(doc.estimated_value),
        accounting_document_type="Board Remnant",
        accounting_document=doc.name,
        remarks=f"{DEMO_TAG} Reusable remainder recovered from replacement board",
    )
    frappe.db.set_value("Board Remnant", doc.name, "recovery_cost_ledger", ledger.name, update_modified=False)
    sync_factory_order_actual_costs(cutting.factory_order)
    return doc.name


def _ensure_alerts(context, scenario_results):
    by_code = {row["scenario"]: row for row in scenario_results}
    definitions = []
    delayed = by_code.get("DELAYED-BLOCKED")
    damaged = by_code.get("DAMAGED-REMNANT")
    if delayed:
        definitions.extend([
            {
                "key": f"{context['prefix']}|Order Delay|{delayed['factory_order']}",
                "type": "Order Delay",
                "severity": "Critical",
                "status": "Escalated",
                "reference_doctype": "Factory Order",
                "reference_name": delayed["factory_order"],
                "description": "Demo order is three days late",
                "responsible": context["users"].get("planner"),
                "escalated_to": context["users"].get("supervisor"),
                "count": 3,
            },
            {
                "key": f"{context['prefix']}|Blocked Stage|{delayed['factory_order']}",
                "type": "Blocked Production Stage",
                "severity": "High",
                "status": "Open",
                "reference_doctype": "Factory Order",
                "reference_name": delayed["factory_order"],
                "description": "Edge banding has remained blocked for more than eight hours",
                "responsible": context["users"].get("Edge Banding"),
                "escalated_to": context["users"].get("supervisor"),
                "count": 2,
            },
        ])
    if damaged and damaged.get("piece_exception"):
        definitions.append({
            "key": f"{context['prefix']}|Piece Exception|{damaged['piece_exception']}",
            "type": "Piece Exception",
            "severity": "High",
            "status": "Acknowledged",
            "reference_doctype": "Piece Exception",
            "reference_name": damaged["piece_exception"],
            "description": "Damaged replacement is waiting for cutting from a reserved remnant",
            "responsible": context["users"].get("supervisor"),
            "escalated_to": None,
            "count": 1,
        })
    if context.get("maintenance_workstation"):
        definitions.append({
            "key": f"{context['prefix']}|Workstation|{context['maintenance_workstation']}",
            "type": "Workstation Unavailable",
            "severity": "High",
            "status": "Open",
            "reference_doctype": "Factory Workstation",
            "reference_name": context["maintenance_workstation"],
            "description": "Second edge bander is under scheduled maintenance",
            "responsible": context["users"].get("supervisor"),
            "escalated_to": None,
            "count": 1,
        })

    for definition in definitions:
        if frappe.db.exists("Factory Alert Log", {"alert_key": definition["key"]}):
            continue
        now = now_datetime()
        doc = frappe.new_doc("Factory Alert Log")
        doc.update({
            "alert_key": definition["key"],
            "alert_type": definition["type"],
            "severity": definition["severity"],
            "status": definition["status"],
            "reference_doctype": definition["reference_doctype"],
            "reference_name": definition["reference_name"],
            "description": f"{DEMO_TAG} {definition['description']}",
            "responsible": definition["responsible"],
            "escalated_to": definition["escalated_to"],
            "first_detected_at": add_to_date(now, hours=-12),
            "last_detected_at": now,
            "last_notified_at": add_to_date(now, hours=-1),
            "notification_count": definition["count"],
            "acknowledged_at": add_to_date(now, hours=-2) if definition["status"] == "Acknowledged" else None,
            "acknowledged_by": definition["responsible"] if definition["status"] == "Acknowledged" else None,
            "escalated_at": add_to_date(now, hours=-4) if definition["status"] == "Escalated" else None,
        })
        doc.insert(ignore_permissions=True)


def _status(context):
    scenarios = []
    for scenario in SCENARIOS:
        marker = _sales_marker(context, scenario)
        sales_order = frappe.db.get_value("Sales Order", {"po_no": marker, "company": context["company"]}, "name")
        factory_order = frappe.db.get_value("Factory Order", {"sales_order": sales_order}, "name") if sales_order else None
        scenarios.append({
            "code": scenario["code"],
            "description": scenario["description"],
            "sales_order": sales_order,
            "factory_order": factory_order,
            "status": frappe.db.get_value("Factory Order", factory_order, "status") if factory_order else "Missing",
        })
    return {
        "company": context["company"],
        "prefix": context["prefix"],
        "ready": all(row["factory_order"] for row in scenarios),
        "counts": {
            "items": frappe.db.count("Item", {"item_code": ["like", f"{context['prefix']}-%"]}),
            "customers": frappe.db.count("Customer", {"customer_name": ["like", f"DEMO {context['abbr']} - %"]}),
            "workstations": frappe.db.count("Factory Workstation", {"name": ["like", f"DEMO {context['abbr']} %"]}),
            "users": frappe.db.count("User", {"name": ["like", f"wf.demo.{context['abbr'].lower()}.%@example.com"]}),
            "factory_orders": sum(1 for row in scenarios if row["factory_order"]),
            "piece_exceptions": frappe.db.count("Piece Exception", {"reason": ["like", f"%{DEMO_TAG}%"]}),
            "remnants": frappe.db.count("Board Remnant", {"notes": ["like", f"%{DEMO_TAG}%{context['abbr']}%"]}),
            "alerts": frappe.db.count("Factory Alert Log", {"alert_key": ["like", f"{context['prefix']}|%"]}),
        },
        "scenarios": scenarios,
        "notes": [
            "Demo users are disabled and no welcome emails are sent.",
            "Generation is idempotent and never deletes production records.",
            "Material valuation ledger rows are explicitly marked synthetic; they are not presented as Material Issue Stock Entries.",
        ],
    }
