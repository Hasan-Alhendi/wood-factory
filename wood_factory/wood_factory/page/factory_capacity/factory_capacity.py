import frappe
from frappe.utils import flt

from wood_factory.security import require_planning


STAGES = ["Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing"]
CAPACITY_FIELDS = {
    "Cutting": "cutting_minutes_per_day", "Edge Banding": "edge_banding_minutes_per_day",
    "Drilling": "drilling_minutes_per_day", "Assembly": "assembly_minutes_per_day",
    "Quality Inspection": "quality_inspection_minutes_per_day", "Packing": "packing_minutes_per_day",
}
DEFAULT_ESTIMATES = {"Cutting": 60, "Edge Banding": 45, "Drilling": 30, "Assembly": 60, "Quality Inspection": 20, "Packing": 30}
ACTIVE = ["Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing"]


@frappe.whitelist()
def get_capacity_plan():
    require_planning()
    settings = frappe.get_single("Factory Capacity Settings")
    planning_days = settings.planning_days or 5
    history = dict(frappe.db.sql("""select stage, avg(actual_minutes) from `tabFactory Order Stage` where status='Completed' and actual_minutes > 0 group by stage"""))
    pending = frappe.db.sql("""
        select s.stage, count(*) as orders from `tabFactory Order Stage` s
        inner join `tabFactory Order` o on o.name=s.parent
        where o.status in %(statuses)s and s.status in ('Pending','Ready','In Progress','Blocked') group by s.stage
    """, {"statuses": ACTIVE}, as_dict=True)
    workstations = frappe.get_all(
        "Factory Workstation",
        fields=["name", "stage", "status", "minutes_per_day", "efficiency_percent", "effective_minutes_per_day", "unavailable_reason"],
        limit_page_length=0,
    )
    pending_map = {row.stage: row.orders for row in pending}
    by_stage = {stage: [] for stage in STAGES}
    for workstation in workstations:
        by_stage.setdefault(workstation.stage, []).append(workstation)
    rows = []
    for stage in STAGES:
        queued = pending_map.get(stage, 0)
        avg_minutes = flt(history.get(stage) or DEFAULT_ESTIMATES[stage], 2)
        required = flt(queued * avg_minutes, 2)
        stage_workstations = by_stage.get(stage, [])
        active_workstations = [row for row in stage_workstations if row.status == "Active"]
        if stage_workstations:
            daily_capacity = flt(sum(flt(row.effective_minutes_per_day) for row in active_workstations), 2)
            capacity_source = "Workstations"
        else:
            daily_capacity = flt(settings.get(CAPACITY_FIELDS[stage]) or 480, 2)
            capacity_source = "Stage Setting"
        horizon_capacity = daily_capacity * planning_days
        load_percent = flt(required / horizon_capacity * 100, 2) if horizon_capacity else (999 if required else 0)
        days_required = flt(required / daily_capacity, 2) if daily_capacity else None
        risk = "No Capacity" if required and not daily_capacity else "Critical" if load_percent > 100 else "High" if load_percent >= 80 else "Watch" if load_percent >= 60 else "Healthy"
        rows.append({"stage": stage, "queued_orders": queued, "avg_minutes": avg_minutes, "required_minutes": required, "daily_capacity": daily_capacity, "load_percent": load_percent, "days_required": days_required, "risk": risk, "capacity_source": capacity_source, "workstations": len(stage_workstations), "active_workstations": len(active_workstations)})
    bottlenecks = sorted([row for row in rows if row["queued_orders"]], key=lambda row: (-row["load_percent"], -row["required_minutes"]))[:3]
    unavailable = [row for row in workstations if row.status != "Active"]
    return {"planning_days": planning_days, "stages": rows, "bottlenecks": bottlenecks, "unavailable_workstations": unavailable, "summary": {"critical": sum(1 for row in rows if row["risk"] in ("Critical", "No Capacity")), "high": sum(1 for row in rows if row["risk"] == "High"), "queued_stage_work": sum(row["queued_orders"] for row in rows), "max_load": max((row["load_percent"] for row in rows), default=0), "active_workstations": sum(1 for row in workstations if row.status == "Active"), "unavailable_workstations": len(unavailable)}}
