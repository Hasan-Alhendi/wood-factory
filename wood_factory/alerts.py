import frappe
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, nowdate


ACTIVE_ORDER_STATUSES = ["Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing", "Ready for Delivery"]


DEFAULT_SETTINGS = {
    "enabled": 1,
    "primary_manager": "Administrator",
    "escalation_manager": "Administrator",
    "create_todos": 1,
    "system_notifications": 1,
    "email_notifications": 0,
    "blocked_alert_hours": 2,
    "blocked_critical_hours": 8,
    "exception_alert_hours": 4,
    "exception_critical_hours": 24,
    "workstation_alert_hours": 1,
    "workstation_critical_hours": 8,
    "high_escalation_hours": 4,
    "critical_escalation_hours": 1,
    "repeat_notification_hours": 6,
    "auto_resolve": 1,
}


def evaluate_factory_alerts():
    settings = _get_settings()
    if not cint(settings.enabled):
        return []

    alerts = []
    alerts.extend(_delayed_order_alerts())
    alerts.extend(_blocked_stage_alerts(settings))
    alerts.extend(_exception_alerts(settings))
    alerts.extend(_workstation_alerts(settings))
    alerts.extend(_delivery_risk_alerts())

    active_keys = set()
    result = []
    for alert in alerts:
        alert_log = _upsert_alert(alert, settings)
        active_keys.add(alert_log.alert_key)
        _dispatch_alert(alert_log, settings)
        _maybe_escalate(alert_log, settings)
        result.append({
            **alert,
            "alert_log": alert_log.name,
            "status": alert_log.status,
            "escalated_to": alert_log.escalated_to,
        })

    if cint(settings.auto_resolve):
        _resolve_cleared_alerts(active_keys)
    return result


def _get_settings():
    settings = frappe._dict(DEFAULT_SETTINGS.copy())
    try:
        if frappe.db.exists("DocType", "Factory Alert Settings"):
            stored = frappe.get_single("Factory Alert Settings")
            for key in DEFAULT_SETTINGS:
                value = stored.get(key)
                if value is not None:
                    settings[key] = value
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Factory Alert Settings")
    return settings


def _delayed_order_alerts():
    rows = frappe.get_all(
        "Factory Order",
        filters={"status": ["in", ACTIVE_ORDER_STATUSES], "expected_delivery_date": ["is", "set"]},
        fields=["name", "expected_delivery_date", "current_stage", "current_responsible"],
    )
    today = getdate(nowdate())
    alerts = []
    for row in rows:
        delivery = getdate(row.expected_delivery_date)
        if delivery >= today:
            continue
        days = (today - delivery).days
        alerts.append(_alert(
            "Factory Order", row.name, "Delayed Order", "Critical" if days >= 3 else "High",
            row.current_responsible, f"Order is {days} day(s) late at {row.current_stage or 'unknown stage'}",
        ))
    return alerts


def _blocked_stage_alerts(settings):
    rows = frappe.get_all(
        "Factory Order Stage",
        filters={"status": "Blocked", "blocked_at": ["is", "set"]},
        fields=["parent", "stage", "block_reason", "blocked_at", "responsible"],
    )
    now = now_datetime()
    alerts = []
    for row in rows:
        hours = _hours_between(row.blocked_at, now)
        if hours < flt(settings.blocked_alert_hours):
            continue
        alerts.append(_alert(
            "Factory Order", row.parent, "Blocked Production",
            "Critical" if hours >= flt(settings.blocked_critical_hours) else "High",
            row.responsible,
            f"{row.stage} blocked for {hours:.1f} hour(s): {row.block_reason or 'No reason'}",
        ))
    return alerts


def _exception_alerts(settings):
    rows = frappe.get_all(
        "Piece Exception",
        filters={"status": ["not in", ["Resolved", "Cancelled"]]},
        fields=["name", "factory_order", "exception_type", "status", "responsible", "reported_at"],
    )
    now = now_datetime()
    alerts = []
    for row in rows:
        hours = _hours_between(row.reported_at, now) if row.reported_at else 0
        if hours < flt(settings.exception_alert_hours):
            continue
        alerts.append(_alert(
            "Piece Exception", row.name, "Unresolved Piece Exception",
            "Critical" if hours >= flt(settings.exception_critical_hours) else "High",
            row.responsible,
            f"{row.exception_type} for {row.factory_order} remains {row.status} for {hours:.1f} hour(s)",
        ))
    return alerts


def _workstation_alerts(settings):
    rows = frappe.get_all(
        "Factory Workstation",
        filters={"status": ["!=", "Active"]},
        fields=["name", "stage", "status", "unavailable_reason", "modified"],
    )
    now = now_datetime()
    alerts = []
    for row in rows:
        hours = _hours_between(row.modified, now)
        if hours < flt(settings.workstation_alert_hours):
            continue
        alerts.append(_alert(
            "Factory Workstation", row.name, "Unavailable Workstation",
            "Critical" if hours >= flt(settings.workstation_critical_hours) else "High",
            settings.primary_manager,
            f"{row.name} in {row.stage} is {row.status} for {hours:.1f} hour(s): {row.unavailable_reason or 'No reason'}",
        ))
    return alerts


def _delivery_risk_alerts():
    try:
        from wood_factory.wood_factory.page.factory_schedule.factory_schedule import get_production_schedule
        schedule = get_production_schedule()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Factory ETA Alert Evaluation")
        return []

    alerts = []
    for row in schedule.get("orders", []):
        if row.get("eta_risk") not in ("At Risk", "Late"):
            continue
        if flt(row.get("computed_delay_days")) > 0:
            continue
        completion = row.get("estimated_completion")
        alerts.append(_alert(
            "Factory Order", row.name, "Predicted Delivery Risk",
            "Critical" if row.get("eta_risk") == "Late" else "High",
            row.get("current_responsible"),
            f"Order forecast is {row.get('eta_risk')}; estimated completion is {completion or 'unavailable'}",
        ))
    return alerts


def _alert(reference_type, reference_name, alert_type, priority, responsible, description):
    return {
        "reference_type": reference_type,
        "reference_name": reference_name,
        "alert_type": alert_type,
        "priority": priority,
        "responsible": responsible,
        "description": description,
    }


def _upsert_alert(alert, settings):
    key = f"{alert['alert_type']}|{alert['reference_type']}|{alert['reference_name']}"
    name = frappe.db.get_value("Factory Alert Log", {"alert_key": key}, "name")
    now = now_datetime()
    responsible = alert.get("responsible") or settings.primary_manager or "Administrator"
    values = {
        "alert_type": alert["alert_type"],
        "severity": alert["priority"],
        "reference_doctype": alert["reference_type"],
        "reference_name": alert["reference_name"],
        "description": alert["description"],
        "responsible": responsible,
        "last_detected_at": now,
    }
    if name:
        doc = frappe.get_doc("Factory Alert Log", name)
        if doc.status == "Resolved":
            values.update({
                "status": "Open", "resolved_at": None, "acknowledged_at": None,
                "acknowledged_by": None, "escalated_at": None, "escalated_to": None,
                "first_detected_at": now,
            })
        doc.db_set(values)
        doc.reload()
        return doc

    doc = frappe.new_doc("Factory Alert Log")
    doc.update({"alert_key": key, "status": "Open", "first_detected_at": now, **values})
    doc.insert(ignore_permissions=True)
    return doc


def _dispatch_alert(alert_log, settings, force=False, target_user=None, escalation=False):
    now = now_datetime()
    repeat_hours = flt(settings.repeat_notification_hours)
    due = not alert_log.last_notified_at or _hours_between(alert_log.last_notified_at, now) >= repeat_hours
    if not force and not due:
        return

    user = target_user or alert_log.responsible or settings.primary_manager or "Administrator"
    if cint(settings.create_todos):
        _ensure_todo(alert_log, user, escalation=escalation)
    if cint(settings.system_notifications):
        _create_notification_log(alert_log, user, escalation=escalation)
    if cint(settings.email_notifications):
        _send_email(alert_log, user, escalation=escalation)

    alert_log.db_set({
        "last_notified_at": now,
        "notification_count": cint(alert_log.notification_count) + 1,
    })


def _maybe_escalate(alert_log, settings):
    if alert_log.status != "Open" or alert_log.severity not in ("High", "Critical"):
        return
    threshold = flt(settings.critical_escalation_hours if alert_log.severity == "Critical" else settings.high_escalation_hours)
    if _hours_between(alert_log.first_detected_at, now_datetime()) < threshold:
        return
    manager = settings.escalation_manager or settings.primary_manager or "Administrator"
    alert_log.db_set({"status": "Escalated", "escalated_to": manager, "escalated_at": now_datetime()})
    alert_log.reload()
    _dispatch_alert(alert_log, settings, force=True, target_user=manager, escalation=True)


def _ensure_todo(alert_log, allocated_to, escalation=False):
    marker = f"[Factory Alert:{alert_log.name}]"
    existing = frappe.db.exists("ToDo", {
        "allocated_to": allocated_to,
        "reference_type": alert_log.reference_doctype,
        "reference_name": alert_log.reference_name,
        "description": ["like", f"{marker}%"],
        "status": "Open",
    })
    if existing:
        return
    todo = frappe.new_doc("ToDo")
    todo.update({
        "allocated_to": allocated_to,
        "reference_type": alert_log.reference_doctype,
        "reference_name": alert_log.reference_name,
        "description": f"{marker} {'ESCALATED: ' if escalation else ''}{alert_log.description}",
        "priority": "High" if alert_log.severity in ("High", "Critical") else "Medium",
        "status": "Open",
    })
    todo.insert(ignore_permissions=True)


def _create_notification_log(alert_log, user, escalation=False):
    if not user or user == "Guest" or not frappe.db.exists("User", user):
        return
    notification = frappe.new_doc("Notification Log")
    notification.update({
        "subject": f"{'ESCALATED · ' if escalation else ''}{alert_log.severity}: {alert_log.alert_type}",
        "email_content": alert_log.description,
        "for_user": user,
        "type": "Alert",
        "document_type": alert_log.reference_doctype,
        "document_name": alert_log.reference_name,
        "from_user": "Administrator",
    })
    notification.insert(ignore_permissions=True)


def _send_email(alert_log, user, escalation=False):
    email = frappe.db.get_value("User", user, "email") if user else None
    if not email:
        return
    frappe.sendmail(
        recipients=[email],
        subject=f"{'ESCALATED · ' if escalation else ''}{alert_log.severity}: {alert_log.alert_type}",
        message=f"<p>{frappe.utils.escape_html(alert_log.description or '')}</p><p>Reference: {alert_log.reference_doctype} {alert_log.reference_name}</p>",
        delayed=True,
    )


def _resolve_cleared_alerts(active_keys):
    logs = frappe.get_all(
        "Factory Alert Log",
        filters={"status": ["in", ["Open", "Acknowledged", "Escalated"]]},
        fields=["name", "alert_key", "reference_doctype", "reference_name"],
    )
    now = now_datetime()
    for row in logs:
        if row.alert_key in active_keys:
            continue
        frappe.db.set_value("Factory Alert Log", row.name, {"status": "Resolved", "resolved_at": now}, update_modified=False)
        todos = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": row.reference_doctype,
                "reference_name": row.reference_name,
                "description": ["like", f"[Factory Alert:{row.name}]%"],
                "status": "Open",
            },
            pluck="name",
        )
        for todo in todos:
            frappe.db.set_value("ToDo", todo, "status", "Closed", update_modified=False)


def _hours_between(start, end):
    return max((get_datetime(end) - get_datetime(start)).total_seconds() / 3600, 0)
