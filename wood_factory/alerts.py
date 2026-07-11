import frappe
from frappe.utils import date_diff, get_datetime, getdate, now_datetime, nowdate


ACTIVE_ORDER_STATUSES = ["Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing", "Ready for Delivery"]


def evaluate_factory_alerts():
    alerts = []
    alerts.extend(_delayed_order_alerts())
    alerts.extend(_blocked_stage_alerts())
    alerts.extend(_exception_alerts())
    for alert in alerts:
        _ensure_todo(alert)
    return alerts


def _delayed_order_alerts():
    rows = frappe.get_all("Factory Order", filters={"status": ["in", ACTIVE_ORDER_STATUSES], "expected_delivery_date": ["is", "set"]}, fields=["name", "expected_delivery_date", "current_stage", "current_responsible"])
    today = getdate(nowdate())
    return [
        _alert("Factory Order", row.name, "Delayed Order", "Critical" if date_diff(today, getdate(row.expected_delivery_date)) >= 3 else "High", row.current_responsible, f"Order is {date_diff(today, getdate(row.expected_delivery_date))} day(s) late at {row.current_stage}")
        for row in rows if getdate(row.expected_delivery_date) < today
    ]


def _blocked_stage_alerts():
    rows = frappe.get_all("Factory Order Stage", filters={"status": "Blocked", "blocked_at": ["is", "set"]}, fields=["parent", "stage", "block_reason", "blocked_at", "responsible"])
    now = now_datetime()
    alerts = []
    for row in rows:
        hours = max((now - get_datetime(row.blocked_at)).total_seconds() / 3600, 0)
        if hours < 2:
            continue
        alerts.append(_alert("Factory Order", row.parent, "Blocked Production", "Critical" if hours >= 8 else "High", row.responsible, f"{row.stage} blocked for {hours:.1f} hour(s): {row.block_reason or 'No reason'}"))
    return alerts


def _exception_alerts():
    rows = frappe.get_all("Piece Exception", filters={"status": ["not in", ["Resolved", "Cancelled"]]}, fields=["name", "factory_order", "exception_type", "status", "responsible", "reported_at"])
    now = now_datetime()
    alerts = []
    for row in rows:
        hours = max((now - get_datetime(row.reported_at)).total_seconds() / 3600, 0) if row.reported_at else 0
        if hours < 4:
            continue
        alerts.append(_alert("Piece Exception", row.name, "Unresolved Piece Exception", "Critical" if hours >= 24 else "High", row.responsible, f"{row.exception_type} for {row.factory_order} remains {row.status} for {hours:.1f} hour(s)"))
    return alerts


def _alert(reference_type, reference_name, alert_type, priority, responsible, description):
    return {"reference_type": reference_type, "reference_name": reference_name, "alert_type": alert_type, "priority": priority, "responsible": responsible, "description": description}


def _ensure_todo(alert):
    allocated_to = alert.get("responsible") or "Administrator"
    existing = frappe.db.exists("ToDo", {"reference_type": alert["reference_type"], "reference_name": alert["reference_name"], "description": ["like", f"[{alert['alert_type']}]%"], "status": "Open"})
    if existing:
        return
    todo = frappe.new_doc("ToDo")
    todo.update({"allocated_to": allocated_to, "reference_type": alert["reference_type"], "reference_name": alert["reference_name"], "description": f"[{alert['alert_type']}] {alert['description']}", "priority": "High" if alert["priority"] in ("High", "Critical") else "Medium", "status": "Open"})
    todo.insert(ignore_permissions=True)
