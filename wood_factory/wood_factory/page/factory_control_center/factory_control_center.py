import frappe

from wood_factory.wood_factory.page.factory_dashboard.factory_dashboard import get_dashboard_data
from wood_factory.wood_factory.page.factory_schedule.factory_schedule import get_production_schedule


@frappe.whitelist()
def get_control_center_data():
    dashboard = get_dashboard_data()
    schedule = get_production_schedule()
    workstations = frappe.get_all(
        "Factory Workstation",
        fields=["name", "stage", "status", "effective_minutes_per_day", "unavailable_reason"],
        order_by="stage asc, name asc",
    )
    workstation_summary = {
        "total": len(workstations),
        "active": sum(1 for row in workstations if row.status == "Active"),
        "maintenance": sum(1 for row in workstations if row.status == "Maintenance"),
        "out_of_service": sum(1 for row in workstations if row.status == "Out of Service"),
    }
    unavailable = [row for row in workstations if row.status != "Active"]
    alert_logs = frappe.get_all(
        "Factory Alert Log",
        filters={"status": ["in", ["Open", "Acknowledged", "Escalated"]]},
        fields=[
            "name", "alert_type", "severity", "status", "reference_doctype", "reference_name",
            "description", "responsible", "escalated_to", "first_detected_at", "last_detected_at",
        ],
        order_by="first_detected_at asc",
    )
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alert_logs.sort(key=lambda row: (severity_order.get(row.severity, 9), row.first_detected_at or "", row.name))
    alert_summary = {
        "active": len(alert_logs),
        "critical": sum(1 for row in alert_logs if row.severity == "Critical"),
        "escalated": sum(1 for row in alert_logs if row.status == "Escalated"),
        "acknowledged": sum(1 for row in alert_logs if row.status == "Acknowledged"),
    }
    return {
        "dashboard": dashboard,
        "schedule": schedule,
        "workstations": workstation_summary,
        "unavailable_workstations": unavailable[:20],
        "alerts": alert_summary,
        "alert_logs": alert_logs[:30],
        "generated_at": frappe.utils.now_datetime(),
    }
