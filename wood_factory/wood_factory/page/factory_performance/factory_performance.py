import frappe
from frappe.utils import add_days, flt, getdate, nowdate


STAGES = ["Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing"]


@frappe.whitelist()
def get_performance_data(from_date=None, to_date=None):
    to_date = getdate(to_date or nowdate())
    from_date = getdate(from_date or add_days(to_date, -30))
    if from_date > to_date:
        frappe.throw("From Date cannot be after To Date")

    rows = frappe.db.sql("""
        select s.stage, s.actual_minutes, s.blocked_minutes, s.responsible,
               s.started_at, s.completed_at, s.parent as factory_order
        from `tabFactory Order Stage` s
        where s.status = 'Completed'
          and s.completed_at between %(from_date)s and date_add(%(to_date)s, interval 1 day)
        order by s.completed_at asc
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    stage_map = {stage: {"stage": stage, "completed": 0, "work_minutes": 0, "blocked_minutes": 0, "avg_minutes": 0, "blocked_percent": 0} for stage in STAGES}
    user_map = {}
    total_work = total_blocked = 0
    orders = set()

    for row in rows:
        metric = stage_map.setdefault(row.stage, {"stage": row.stage, "completed": 0, "work_minutes": 0, "blocked_minutes": 0, "avg_minutes": 0, "blocked_percent": 0})
        work = flt(row.actual_minutes); blocked = flt(row.blocked_minutes)
        metric["completed"] += 1; metric["work_minutes"] += work; metric["blocked_minutes"] += blocked
        total_work += work; total_blocked += blocked; orders.add(row.factory_order)
        user = row.responsible or "Unassigned"
        worker = user_map.setdefault(user, {"user": user, "completed_stages": 0, "work_minutes": 0, "blocked_minutes": 0})
        worker["completed_stages"] += 1; worker["work_minutes"] += work; worker["blocked_minutes"] += blocked

    for metric in stage_map.values():
        metric["work_minutes"] = flt(metric["work_minutes"], 2); metric["blocked_minutes"] = flt(metric["blocked_minutes"], 2)
        metric["avg_minutes"] = flt(metric["work_minutes"] / metric["completed"], 2) if metric["completed"] else 0
        elapsed = metric["work_minutes"] + metric["blocked_minutes"]
        metric["blocked_percent"] = flt(metric["blocked_minutes"] / elapsed * 100, 2) if elapsed else 0

    workers = sorted(user_map.values(), key=lambda row: (-row["completed_stages"], row["work_minutes"]))
    bottlenecks = sorted(stage_map.values(), key=lambda row: (-row["avg_minutes"], -row["blocked_percent"]))
    return {
        "period": {"from_date": from_date, "to_date": to_date},
        "summary": {"completed_orders": len(orders), "completed_stages": len(rows), "work_hours": flt(total_work / 60, 2), "blocked_hours": flt(total_blocked / 60, 2)},
        "stages": list(stage_map.values()),
        "workers": workers[:20],
        "bottlenecks": [row for row in bottlenecks if row["completed"]][:3],
    }
