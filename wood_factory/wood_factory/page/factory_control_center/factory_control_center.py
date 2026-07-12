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
    return {
        "dashboard": dashboard,
        "schedule": schedule,
        "workstations": workstation_summary,
        "unavailable_workstations": unavailable[:20],
        "generated_at": frappe.utils.now_datetime(),
    }
