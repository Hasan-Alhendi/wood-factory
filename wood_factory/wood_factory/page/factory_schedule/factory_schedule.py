import frappe
from frappe.utils import date_diff, getdate, nowdate


ACTIVE = ["Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing"]
PRIORITY_WEIGHT = {"Urgent": 4000, "High": 3000, "Normal": 2000, "Low": 1000}


@frappe.whitelist()
def get_production_schedule():
    orders = frappe.get_all("Factory Order", filters={"status": ["in", ACTIVE]}, fields=["name", "customer", "status", "priority", "priority_override", "priority_reason", "current_stage", "progress_percent", "expected_delivery_date", "delay_days", "modified"])
    today = getdate(nowdate())
    exception_counts = dict(frappe.db.sql("""select factory_order, count(*) from `tabPiece Exception` where status not in ('Resolved','Cancelled') group by factory_order"""))
    for order in orders:
        delivery = getdate(order.expected_delivery_date) if order.expected_delivery_date else None
        days_left = date_diff(delivery, today) if delivery else 999
        delayed = max(-days_left, 0) if delivery else order.delay_days or 0
        exceptions = exception_counts.get(order.name, 0)
        calculated = "Urgent" if delayed or exceptions else "High" if days_left <= 1 else "Normal" if days_left <= 3 else "Low"
        effective = order.priority_override or calculated
        score = PRIORITY_WEIGHT[effective] + min(delayed, 30) * 100 + exceptions * 75 - min(max(days_left, 0), 90)
        order.update({"priority": effective, "calculated_priority": calculated, "days_left": days_left if delivery else None, "computed_delay_days": delayed, "open_exceptions": exceptions, "schedule_score": score})
    orders.sort(key=lambda row: (-row.schedule_score, row.expected_delivery_date or "9999-12-31", row.modified))
    for index, order in enumerate(orders, 1): order["queue_position"] = index
    return {"orders": orders, "summary": {"queued": len(orders), "urgent": sum(1 for row in orders if row.priority == "Urgent"), "high": sum(1 for row in orders if row.priority == "High"), "with_exceptions": sum(1 for row in orders if row.open_exceptions)}}
