import frappe
from frappe.utils import flt


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
    settings = frappe.get_single("Factory Capacity Settings")
    planning_days = settings.planning_days or 5
    history = dict(frappe.db.sql("""
        select stage, avg(actual_minutes) from `tabFactory Order Stage`
        where status='Completed' and actual_minutes > 0 group by stage
    """))
    pending = frappe.db.sql("""
        select s.stage, count(*) as orders
        from `tabFactory Order Stage` s
        inner join `tabFactory Order` o on o.name=s.parent
        where o.status in %(statuses)s and s.status in ('Pending','Ready','In Progress','Blocked')
        group by s.stage
    """, {"statuses": ACTIVE}, as_dict=True)
    pending_map = {row.stage: row.orders for row in pending}
    rows = []
    for stage in STAGES:
        queued = pending_map.get(stage, 0)
        avg_minutes = flt(history.get(stage) or DEFAULT_ESTIMATES[stage], 2)
        required = flt(queued * avg_minutes, 2)
        daily_capacity = flt(settings.get(CAPACITY_FIELDS[stage]) or 480, 2)
        horizon_capacity = daily_capacity * planning_days
        load_percent = flt(required / horizon_capacity * 100, 2) if horizon_capacity else 0
        days_required = flt(required / daily_capacity, 2) if daily_capacity else 0
        risk = "Critical" if load_percent > 100 else "High" if load_percent >= 80 else "Watch" if load_percent >= 60 else "Healthy"
        rows.append({"stage": stage, "queued_orders": queued, "avg_minutes": avg_minutes, "required_minutes": required, "daily_capacity": daily_capacity, "load_percent": load_percent, "days_required": days_required, "risk": risk})
    bottlenecks = sorted([row for row in rows if row["queued_orders"]], key=lambda row: (-row["load_percent"], -row["required_minutes"]))[:3]
    return {"planning_days": planning_days, "stages": rows, "bottlenecks": bottlenecks, "summary": {"critical": sum(1 for row in rows if row["risk"] == "Critical"), "high": sum(1 for row in rows if row["risk"] == "High"), "queued_stage_work": sum(row["queued_orders"] for row in rows), "max_load": max((row["load_percent"] for row in rows), default=0)}}
