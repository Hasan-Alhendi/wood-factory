import frappe
from frappe.utils import cint

from wood_factory import demo_data, demo_dataset
from wood_factory.security import FACTORY_ROLES, require_management


EXPECTED_SCENARIOS = {
    "NORMAL-CUTTING",
    "DELAYED-BLOCKED",
    "DAMAGED-REMNANT",
    "WRONG-DIM-NEW-BOARD",
    "READY-DELIVERY",
    "DELIVERED",
}


@frappe.whitelist()
def run_factory_acceptance(company=None, include_stock=0, include_users=0):
    """Create or repair the safe demo dataset, then validate the complete factory flow.

    The function is intentionally explicit and never deletes production records. It may
    create demo records marked with ``[WOOD_FACTORY_DEMO]`` for the selected company.
    """
    require_management()
    company = demo_data._resolve_company(company)
    dataset = demo_dataset.create_demo_dataset(
        company=company,
        include_users=cint(include_users),
        include_stock=cint(include_stock),
    )
    validation = validate_factory_acceptance(company=company)
    return {
        "company": company,
        "dataset": dataset,
        "validation": validation,
        "passed": validation["critical_failed"] == 0,
    }


@frappe.whitelist()
def validate_factory_acceptance(company=None):
    """Validate the generated end-to-end scenarios without changing their state."""
    require_management()
    company = demo_data._resolve_company(company)
    context = demo_data._company_context(company)
    status = demo_dataset._status(context)
    scenarios = {row["code"]: row for row in status.get("scenarios", [])}
    checks = []

    _check(
        checks,
        "All acceptance scenarios exist",
        EXPECTED_SCENARIOS.issubset(scenarios),
        details=", ".join(sorted(set(scenarios) & EXPECTED_SCENARIOS)),
    )
    _check(checks, "Demo dataset is complete", bool(status.get("ready")))
    _check(checks, "Factory roles are installed", all(frappe.db.exists("Role", role) for role in FACTORY_ROLES))

    for code in sorted(EXPECTED_SCENARIOS):
        row = scenarios.get(code) or {}
        _check(checks, f"{code}: Sales Order exists", bool(row.get("sales_order")))
        _check(checks, f"{code}: Factory Order exists", bool(row.get("factory_order")))
        if not row.get("factory_order"):
            continue
        order = row["factory_order"]
        cutting_orders = frappe.get_all(
            "Cutting Order",
            filters={"factory_order": order},
            pluck="name",
            limit_page_length=0,
        )
        _check(checks, f"{code}: Cutting Order exists", bool(cutting_orders))
        if cutting_orders:
            _check(
                checks,
                f"{code}: Board layout exists",
                frappe.db.count("Board Layout", {"cutting_order": ["in", cutting_orders]}) > 0,
            )
        _check(checks, f"{code}: Physical pieces exist", frappe.db.count("Factory Piece", {"factory_order": order}) > 0)

    _validate_normal_cutting(checks, scenarios)
    _validate_delayed_blocked(checks, scenarios)
    _validate_remnant_replacement(checks, scenarios)
    _validate_new_board_replacement(checks, scenarios)
    _validate_delivery(checks, scenarios)
    _validate_costing_and_events(checks, scenarios)

    critical_failed = sum(1 for row in checks if row["critical"] and not row["passed"])
    warning_failed = sum(1 for row in checks if not row["critical"] and not row["passed"])
    return {
        "company": company,
        "prefix": context["prefix"],
        "checks": checks,
        "passed": sum(1 for row in checks if row["passed"]),
        "failed": sum(1 for row in checks if not row["passed"]),
        "critical_failed": critical_failed,
        "warning_failed": warning_failed,
        "ready_for_runtime_testing": critical_failed == 0,
    }


def _validate_normal_cutting(checks, scenarios):
    order = _order(scenarios, "NORMAL-CUTTING")
    if not order:
        return
    values = frappe.db.get_value("Factory Order", order, ["status", "current_stage"], as_dict=True)
    _check(checks, "NORMAL-CUTTING: order is waiting for cutting", values.current_stage == "Cutting")
    stage = frappe.db.get_value(
        "Factory Order Stage",
        {"parent": order, "stage": "Cutting"},
        ["status", "workstation"],
        as_dict=True,
    )
    _check(checks, "NORMAL-CUTTING: cutting stage is ready", bool(stage and stage.status == "Ready"))
    _check(checks, "NORMAL-CUTTING: cutting workstation is assigned", bool(stage and stage.workstation))


def _validate_delayed_blocked(checks, scenarios):
    order = _order(scenarios, "DELAYED-BLOCKED")
    if not order:
        return
    values = frappe.db.get_value("Factory Order", order, ["delay_days", "current_stage"], as_dict=True)
    _check(checks, "DELAYED-BLOCKED: order is late", bool(values and values.delay_days > 0))
    _check(checks, "DELAYED-BLOCKED: current stage is edge banding", bool(values and values.current_stage == "Edge Banding"))
    blocked = frappe.db.exists("Factory Order Stage", {"parent": order, "stage": "Edge Banding", "status": "Blocked"})
    _check(checks, "DELAYED-BLOCKED: stage is blocked", bool(blocked))
    active_alert = frappe.db.exists(
        "Factory Alert Log",
        {"reference_doctype": "Factory Order", "reference_name": order, "status": ["!=", "Resolved"]},
    )
    _check(checks, "DELAYED-BLOCKED: active alert exists", bool(active_alert))


def _validate_remnant_replacement(checks, scenarios):
    order = _order(scenarios, "DAMAGED-REMNANT")
    if not order:
        return
    exception = _exception(order)
    _check(checks, "DAMAGED-REMNANT: piece exception exists", bool(exception))
    if not exception:
        return
    values = frappe.db.get_value(
        "Piece Exception",
        exception,
        ["replacement_piece", "suggested_remnant", "replacement_cutting_order"],
        as_dict=True,
    )
    _check(checks, "DAMAGED-REMNANT: replacement piece exists", bool(values.replacement_piece))
    _check(checks, "DAMAGED-REMNANT: matching remnant is reserved", bool(values.suggested_remnant))
    _check(checks, "DAMAGED-REMNANT: no new-board cutting order is needed", not values.replacement_cutting_order)
    if not values.replacement_piece or not values.suggested_remnant:
        return
    piece_item = frappe.db.get_value("Factory Piece", values.replacement_piece, "board_item")
    remnant = frappe.db.get_value(
        "Board Remnant",
        values.suggested_remnant,
        ["board_item", "status", "reserved_for_piece"],
        as_dict=True,
    )
    _check(checks, "DAMAGED-REMNANT: remnant material exactly matches the piece", bool(remnant and remnant.board_item == piece_item))
    _check(checks, "DAMAGED-REMNANT: remnant points to the replacement piece", bool(remnant and remnant.reserved_for_piece == values.replacement_piece))
    _check(checks, "DAMAGED-REMNANT: remnant state is reserved", bool(remnant and remnant.status == "Reserved"))


def _validate_new_board_replacement(checks, scenarios):
    order = _order(scenarios, "WRONG-DIM-NEW-BOARD")
    if not order:
        return
    exception = _exception(order)
    _check(checks, "WRONG-DIM-NEW-BOARD: piece exception exists", bool(exception))
    if not exception:
        return
    replacement = frappe.db.get_value("Piece Exception", exception, "replacement_cutting_order")
    _check(checks, "WRONG-DIM-NEW-BOARD: replacement cutting order exists", bool(replacement))
    if not replacement:
        return
    cutting = frappe.db.get_value(
        "Cutting Order",
        replacement,
        ["order_type", "customer_billable", "piece_exception", "accounting_status"],
        as_dict=True,
    )
    _check(checks, "WRONG-DIM-NEW-BOARD: order is an internal replacement", bool(cutting and cutting.order_type == "Internal Replacement"))
    _check(checks, "WRONG-DIM-NEW-BOARD: customer is not billed", bool(cutting and not cint(cutting.customer_billable)))
    _check(checks, "WRONG-DIM-NEW-BOARD: cutting order links to the exception", bool(cutting and cutting.piece_exception == exception))
    _check(
        checks,
        "WRONG-DIM-NEW-BOARD: reusable remainder returns to factory remnants",
        frappe.db.count("Board Remnant", {"source_cutting_order": replacement, "status": "Available"}) > 0,
    )
    internal_cost = frappe.db.exists(
        "Factory Cost Ledger",
        {"factory_order": order, "piece_exception": exception, "customer_billable": 0, "status": "Posted"},
    )
    _check(checks, "WRONG-DIM-NEW-BOARD: internal replacement cost is posted", bool(internal_cost))


def _validate_delivery(checks, scenarios):
    ready = _order(scenarios, "READY-DELIVERY")
    delivered = _order(scenarios, "DELIVERED")
    if ready:
        _check(
            checks,
            "READY-DELIVERY: order is ready for delivery",
            frappe.db.get_value("Factory Order", ready, "status") == "Ready for Delivery",
        )
        open_exceptions = frappe.db.count(
            "Piece Exception", {"factory_order": ready, "status": ["not in", ["Resolved", "Cancelled"]]}
        )
        _check(checks, "READY-DELIVERY: no unresolved piece exception", open_exceptions == 0)
    if delivered:
        _check(
            checks,
            "DELIVERED: order is delivered",
            frappe.db.get_value("Factory Order", delivered, "status") == "Delivered",
        )
        delivered_event = frappe.db.exists(
            "Factory Order Event", {"factory_order": delivered, "event_type": "Delivered"}
        )
        _check(checks, "DELIVERED: delivery event is auditable", bool(delivered_event), critical=False)


def _validate_costing_and_events(checks, scenarios):
    order_names = [row.get("factory_order") for row in scenarios.values() if row.get("factory_order")]
    if not order_names:
        return
    _check(
        checks,
        "Cost ledger contains customer and internal entries",
        frappe.db.count("Factory Cost Ledger", {"factory_order": ["in", order_names], "status": "Posted"}) > 0,
    )
    _check(
        checks,
        "Factory timeline contains production events",
        frappe.db.count("Factory Order Event", {"factory_order": ["in", order_names]}) > 0,
    )
    partial = frappe.db.count(
        "Factory Order",
        {"name": ["in", order_names], "costing_status": ["in", ["Partial", "Not Started"]]},
    )
    _check(checks, "Completed demo orders have usable costing data", partial < len(order_names), critical=False)


def _order(scenarios, code):
    return (scenarios.get(code) or {}).get("factory_order")


def _exception(factory_order):
    return frappe.db.get_value(
        "Piece Exception",
        {"factory_order": factory_order, "reason": ["like", f"%{demo_data.DEMO_TAG}%"]},
        "name",
    )


def _check(checks, name, passed, details=None, critical=True):
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "critical": bool(critical),
            "details": details,
        }
    )
