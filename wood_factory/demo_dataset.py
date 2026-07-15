import frappe
from frappe.utils import cint

from wood_factory import demo_data
from wood_factory.security import require_management


@frappe.whitelist()
def get_demo_status(company=None):
    require_management()
    context = demo_data._company_context(demo_data._resolve_company(company))
    return _status(context)


@frappe.whitelist()
def create_demo_dataset(company=None, include_users=1, include_stock=1):
    """Create or repair the complete demo dataset without duplicating terminal events."""
    require_management()
    from wood_factory.setup import ensure_factory_roles

    ensure_factory_roles()
    context = demo_data._company_context(demo_data._resolve_company(company))
    demo_data._validate_accounting_company(context["company"])
    warnings = []
    results = []

    frappe.db.savepoint("wood_factory_demo_dataset")
    try:
        demo_data._ensure_master_data(context, include_users=cint(include_users))
        if cint(include_stock):
            try:
                context["stock_receipt"] = demo_data._ensure_stock_receipt(context)
            except Exception as exc:
                warnings.append(f"Demo stock receipt was skipped: {exc}")
                frappe.log_error(frappe.get_traceback(), "Wood Factory demo stock receipt")

        for scenario in demo_data.SCENARIOS:
            try:
                results.append(_ensure_scenario(context, scenario, warnings))
            except Exception as exc:
                warnings.append(f"{scenario['code']}: {exc}")
                frappe.log_error(frappe.get_traceback(), f"Wood Factory demo scenario {scenario['code']}")

        demo_data._ensure_alerts(context, results)
    except Exception:
        frappe.db.rollback(save_point="wood_factory_demo_dataset")
        raise

    output = _status(context)
    output.update({"created_or_refreshed": results, "warnings": warnings})
    return output


def _status(context):
    data = demo_data._status(context)
    order_names = [row["factory_order"] for row in data.get("scenarios", []) if row.get("factory_order")]
    cutting_orders = frappe.get_all(
        "Cutting Order",
        filters={"factory_order": ["in", order_names]},
        pluck="name",
        limit_page_length=0,
    ) if order_names else []
    data.setdefault("counts", {})["piece_exceptions"] = frappe.db.count(
        "Piece Exception", {"factory_order": ["in", order_names]}
    ) if order_names else 0
    data["counts"]["remnants"] = frappe.db.count(
        "Board Remnant", {"source_cutting_order": ["in", cutting_orders]}
    ) if cutting_orders else 0
    return data


def _ensure_scenario(context, scenario, warnings):
    sales_order = demo_data._ensure_sales_order(context, scenario)
    order = demo_data._ensure_factory_order(context, scenario, sales_order)
    cutting = demo_data._ensure_cutting_order(context, scenario, order, warnings)
    terminal_status = order.status if scenario["completed_stages"] >= len(demo_data.STAGES) and order.status in ("Ready for Delivery", "Delivered") else None

    demo_data._apply_stage_profile(context, scenario, order)
    if terminal_status:
        values = {"status": terminal_status, "current_stage": None, "current_responsible": None}
        if terminal_status == "Delivered":
            values["delay_days"] = 0
        frappe.db.set_value("Factory Order", order.name, values, update_modified=False)

    demo_data._seed_customer_material_cost(context, scenario, order, cutting)
    demo_data._seed_completed_stage_costs(context, order)
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


def _ensure_exception(context, scenario, order, cutting, warnings):
    existing = frappe.db.get_value(
        "Piece Exception",
        {"factory_order": order.name, "reason": ["like", f"%{demo_data.DEMO_TAG}%"]},
        "name",
    )
    if not existing:
        return demo_data._ensure_exception(context, scenario, order, cutting, warnings)

    exception = frappe.get_doc("Piece Exception", existing)
    if exception.status in ("Resolved", "Cancelled"):
        return exception.name
    if exception.status == "Open":
        exception.require_replacement()
        exception.reload()
    if exception.status == "Replacement Required" and not exception.replacement_piece:
        exception.start_replacement()
        exception.reload()
    if not exception.replacement_piece:
        return exception.name

    if scenario["exception_mode"] == "remnant":
        replacement = frappe.get_doc("Factory Piece", exception.replacement_piece)
        if not exception.suggested_remnant:
            demo_data._ensure_available_remnant(context, scenario, cutting, replacement)
            try:
                exception.find_best_remnant()
            except Exception as exc:
                warnings.append(f"{scenario['code']} remnant reservation: {exc}")
        return exception.name

    if not exception.replacement_cutting_order:
        try:
            exception.create_replacement_cutting_order()
            exception.reload()
        except Exception as exc:
            warnings.append(f"{scenario['code']} replacement creation: {exc}")
            return exception.name
    replacement_cutting = frappe.get_doc("Cutting Order", exception.replacement_cutting_order)
    if not frappe.db.exists("Board Layout", {"cutting_order": replacement_cutting.name}):
        try:
            replacement_cutting.optimize_layout()
            replacement_cutting.reload()
        except Exception as exc:
            warnings.append(f"{scenario['code']} replacement optimization: {exc}")
            return exception.name
    demo_data._seed_internal_replacement_cost(context, order, replacement_cutting, exception)
    demo_data._ensure_recovered_remnant(context, scenario, replacement_cutting, exception)
    return exception.name
