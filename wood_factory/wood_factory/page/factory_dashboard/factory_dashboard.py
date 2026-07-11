import frappe
from frappe.utils import cint, date_diff, getdate, nowdate


ACTIVE_ORDER_STATUSES = [
    "Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing", "Ready for Delivery"
]
STAGES = ["Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing"]


@frappe.whitelist()
def get_dashboard_data():
    orders = frappe.get_all(
        "Factory Order",
        filters={"status": ["in", ACTIVE_ORDER_STATUSES]},
        fields=["name", "customer", "status", "current_stage", "progress_percent", "expected_delivery_date", "delay_days", "current_responsible", "modified"],
        order_by="expected_delivery_date asc, modified asc",
    )
    today = getdate(nowdate())
    for order in orders:
        delivery = getdate(order.expected_delivery_date) if order.expected_delivery_date else None
        order["computed_delay_days"] = max(date_diff(today, delivery), 0) if delivery else cint(order.delay_days)
        order["is_delayed"] = order["computed_delay_days"] > 0

    stage_counts = {stage: 0 for stage in STAGES}
    for order in orders:
        if order.current_stage in stage_counts:
            stage_counts[order.current_stage] += 1

    exceptions = frappe.get_all(
        "Piece Exception",
        filters={"status": ["not in", ["Resolved", "Cancelled"]]},
        fields=["name", "factory_piece", "factory_order", "exception_type", "reported_stage", "status", "responsible", "reported_at"],
        order_by="reported_at asc",
    )
    blocked_stages = frappe.get_all(
        "Factory Order Stage",
        filters={"status": "Blocked"},
        fields=["parent", "stage", "block_reason", "blocked_at", "responsible"],
        order_by="blocked_at asc",
    )

    delayed = sorted((order for order in orders if order["is_delayed"]), key=lambda row: (-row["computed_delay_days"], row["name"]))
    return {
        "summary": {
            "active_orders": len(orders),
            "delayed_orders": len(delayed),
            "blocked_orders": len({row.parent for row in blocked_stages}),
            "open_exceptions": len(exceptions),
            "ready_for_delivery": sum(1 for order in orders if order.status == "Ready for Delivery"),
        },
        "stage_counts": stage_counts,
        "delayed_orders": delayed[:20],
        "blocked_stages": blocked_stages[:20],
        "exceptions": exceptions[:20],
    }
