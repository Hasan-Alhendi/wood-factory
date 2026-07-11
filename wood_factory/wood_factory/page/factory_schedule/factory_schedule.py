import frappe
from frappe.utils import add_to_date, date_diff, flt, get_datetime, getdate, now_datetime, nowdate


ACTIVE = ["Ready for Production", "In Production", "Quality Inspection", "Rework", "Packing"]
PRIORITY_WEIGHT = {"Urgent": 4000, "High": 3000, "Normal": 2000, "Low": 1000}
DEFAULT_ESTIMATES = {"Cutting": 60, "Edge Banding": 45, "Drilling": 30, "Assembly": 60, "Quality Inspection": 20, "Packing": 30}


@frappe.whitelist()
def get_production_schedule():
    orders = _get_scheduled_orders()
    _apply_eta_forecast(orders)
    bottlenecks = get_bottleneck_analysis()
    return {"orders": orders, "summary": _summary(orders), "bottlenecks": bottlenecks}


@frappe.whitelist()
def get_bottleneck_analysis():
    history = dict(frappe.db.sql("""select stage, avg(actual_minutes) from `tabFactory Order Stage` where status='Completed' and actual_minutes > 0 group by stage"""))
    workstations = frappe.get_all("Factory Workstation", filters={"status": "Active"}, fields=["name", "stage", "effective_minutes_per_day"])
    stage_capacity = {}
    workstation_capacity = {}
    for row in workstations:
        capacity = max(flt(row.effective_minutes_per_day), 0)
        workstation_capacity[row.name] = capacity
        stage_capacity[row.stage] = stage_capacity.get(row.stage, 0) + capacity
    rows = frappe.db.sql("""
        select s.parent, s.stage, s.workstation, s.status, s.started_at, o.priority
        from `tabFactory Order Stage` s
        inner join `tabFactory Order` o on o.name=s.parent
        where o.status in %(active)s and s.status in ('Ready','In Progress','Blocked')
    """, {"active": ACTIVE}, as_dict=True)
    stages = {}
    workstation_load = {}
    now = now_datetime()
    for row in rows:
        estimate = flt(history.get(row.stage) or DEFAULT_ESTIMATES.get(row.stage, 30), 2)
        if row.status == "In Progress" and row.started_at:
            elapsed = max((get_datetime(now) - get_datetime(row.started_at)).total_seconds() / 60, 0)
            estimate = max(estimate - elapsed, 5)
        data = stages.setdefault(row.stage, {"stage": row.stage, "load_minutes": 0, "waiting_orders": 0, "blocked_orders": 0, "in_progress": 0, "urgent_orders": 0, "workstations": {}})
        data["load_minutes"] += estimate
        data["waiting_orders"] += 1 if row.status in ("Ready", "Blocked") else 0
        data["blocked_orders"] += 1 if row.status == "Blocked" else 0
        data["in_progress"] += 1 if row.status == "In Progress" else 0
        data["urgent_orders"] += 1 if row.priority == "Urgent" else 0
        if row.workstation:
            workstation_load[row.workstation] = workstation_load.get(row.workstation, 0) + estimate
            data["workstations"][row.workstation] = data["workstations"].get(row.workstation, 0) + estimate
    analysis = []
    for stage, data in stages.items():
        capacity = stage_capacity.get(stage, 0)
        data["capacity_minutes_per_day"] = capacity
        data["load_percent"] = round(data["load_minutes"] / capacity * 100, 1) if capacity else 999
        data["queue_delay_days"] = round(data["load_minutes"] / capacity, 2) if capacity else None
        station_rows = []
        for name, load in data["workstations"].items():
            station_capacity = workstation_capacity.get(name, 0)
            station_rows.append({"workstation": name, "load_minutes": round(load, 2), "load_percent": round(load / station_capacity * 100, 1) if station_capacity else 999})
        station_rows.sort(key=lambda item: (-item["load_percent"], item["workstation"]))
        data["workstations"] = station_rows
        data["primary_workstation"] = station_rows[0]["workstation"] if station_rows else None
        data["severity"] = "Critical" if data["load_percent"] >= 150 or not capacity else "Bottleneck" if data["load_percent"] >= 100 else "Watch" if data["load_percent"] >= 75 else "Healthy"
        analysis.append(data)
    analysis.sort(key=lambda item: (-item["load_percent"], -item["waiting_orders"], item["stage"]))
    for index, item in enumerate(analysis, 1):
        item["rank"] = index
        item["is_current_bottleneck"] = index == 1 and item["severity"] != "Healthy"
    return analysis


@frappe.whitelist()
def simulate_production(workstation=None, downtime_days=0, urgent_order=None, urgent_minutes=0):
    orders = _get_scheduled_orders()
    _apply_eta_forecast(orders)
    baseline = {row.name: {"completion": row.estimated_completion, "risk": row.eta_risk} for row in orders}
    scenario = {"workstation": workstation, "downtime_days": flt(downtime_days), "urgent_order": urgent_order, "urgent_minutes": flt(urgent_minutes)}
    _apply_eta_forecast(orders, scenario=scenario)
    impacts = []
    for order in orders:
        before = baseline[order.name]
        before_dt, after_dt = before["completion"], order.estimated_completion
        shift_hours = round(max((get_datetime(after_dt) - get_datetime(before_dt)).total_seconds() / 3600, 0), 2) if before_dt and after_dt else 0
        if shift_hours or before["risk"] != order.eta_risk:
            impacts.append({"order": order.name, "customer": order.customer, "before_completion": before_dt, "after_completion": after_dt, "before_risk": before["risk"], "after_risk": order.eta_risk, "shift_hours": shift_hours})
    impacts.sort(key=lambda row: (-row["shift_hours"], row["order"]))
    return {"scenario": scenario, "impacts": impacts, "summary": {"affected": len(impacts), "new_at_risk": sum(1 for row in impacts if row["before_risk"] not in ("At Risk", "Late") and row["after_risk"] in ("At Risk", "Late")), "late_after": sum(1 for row in orders if row.eta_risk == "Late"), "max_shift_hours": max([row["shift_hours"] for row in impacts] or [0])}}


def _get_scheduled_orders():
    orders = frappe.get_all("Factory Order", filters={"status": ["in", ACTIVE]}, fields=["name", "customer", "status", "priority", "priority_override", "priority_reason", "current_stage", "progress_percent", "expected_delivery_date", "delay_days", "modified"])
    today = getdate(nowdate())
    exception_counts = dict(frappe.db.sql("""select factory_order, count(*) from `tabPiece Exception` where status not in ('Resolved','Cancelled') group by factory_order"""))
    current_assignments = {row.parent: row for row in frappe.db.sql("""select parent, stage, workstation, status from `tabFactory Order Stage` where status in ('Ready','In Progress','Blocked') order by idx""", as_dict=True)}
    for order in orders:
        delivery = getdate(order.expected_delivery_date) if order.expected_delivery_date else None
        days_left = date_diff(delivery, today) if delivery else 999
        delayed = max(-days_left, 0) if delivery else order.delay_days or 0
        exceptions = exception_counts.get(order.name, 0)
        calculated = "Urgent" if delayed or exceptions else "High" if days_left <= 1 else "Normal" if days_left <= 3 else "Low"
        effective = order.priority_override or calculated
        score = PRIORITY_WEIGHT[effective] + min(delayed, 30) * 100 + exceptions * 75 - min(max(days_left, 0), 90)
        assignment = current_assignments.get(order.name)
        order.update({"priority": effective, "calculated_priority": calculated, "days_left": days_left if delivery else None, "computed_delay_days": delayed, "open_exceptions": exceptions, "schedule_score": score, "workstation": assignment.workstation if assignment else None, "stage_status": assignment.status if assignment else None})
    orders.sort(key=lambda row: (-row.schedule_score, row.expected_delivery_date or "9999-12-31", row.modified))
    for index, order in enumerate(orders, 1): order["queue_position"] = index
    return orders


def _summary(orders):
    return {"queued": len(orders), "urgent": sum(1 for row in orders if row.priority == "Urgent"), "high": sum(1 for row in orders if row.priority == "High"), "with_exceptions": sum(1 for row in orders if row.open_exceptions), "unassigned": sum(1 for row in orders if row.current_stage and not row.workstation), "at_risk": sum(1 for row in orders if row.eta_risk in ("At Risk", "Late"))}


def _apply_eta_forecast(orders, scenario=None):
    scenario = scenario or {}
    history = dict(frappe.db.sql("""select stage, avg(actual_minutes) from `tabFactory Order Stage` where status='Completed' and actual_minutes > 0 group by stage"""))
    capacities = {row.name: flt(row.effective_minutes_per_day) for row in frappe.get_all("Factory Workstation", filters={"status": "Active"}, fields=["name", "effective_minutes_per_day"])}
    stage_rows = frappe.db.sql("""select parent, idx, stage, workstation, status, started_at, actual_minutes from `tabFactory Order Stage` where parent in %(orders)s and status not in ('Completed','Skipped') order by parent, idx""", {"orders": [row.name for row in orders] or [""]}, as_dict=True)
    stages_by_order = {}
    for row in stage_rows: stages_by_order.setdefault(row.parent, []).append(row)
    workstation_available = {name: now_datetime() for name in capacities}
    if scenario.get("workstation") and scenario.get("downtime_days"):
        workstation_available[scenario["workstation"]] = add_to_date(now_datetime(), days=flt(scenario["downtime_days"]))
    ordered = sorted(orders, key=lambda row: (0 if scenario.get("urgent_order") == row.name else 1, row.queue_position))
    urgent_applied = False
    for order in ordered:
        cursor = now_datetime(); breakdown = []
        for stage in stages_by_order.get(order.name, []):
            minutes = flt(history.get(stage.stage) or DEFAULT_ESTIMATES.get(stage.stage, 30), 2)
            if scenario.get("urgent_order") == order.name and not urgent_applied:
                minutes += max(flt(scenario.get("urgent_minutes")), 0); urgent_applied = True
            if stage.status == "In Progress" and stage.started_at:
                elapsed = max((get_datetime(now_datetime()) - get_datetime(stage.started_at)).total_seconds() / 60, 0); minutes = max(minutes - elapsed, 5)
            capacity = capacities.get(stage.workstation, 480)
            start = max(cursor, workstation_available.get(stage.workstation, cursor)) if stage.workstation else cursor
            duration_days = minutes / max(capacity, 1)
            finish = add_to_date(start, hours=duration_days * 24)
            if stage.workstation: workstation_available[stage.workstation] = finish
            breakdown.append({"stage": stage.stage, "workstation": stage.workstation, "minutes": minutes, "start": start, "finish": finish}); cursor = finish
        order["estimated_completion"] = cursor if breakdown else None; order["eta_breakdown"] = breakdown
        delivery = get_datetime(order.expected_delivery_date) if order.expected_delivery_date else None
        if not breakdown: order["eta_risk"] = "No Forecast"
        elif delivery and cursor.date() > delivery.date(): order["eta_risk"] = "Late"
        elif delivery and date_diff(delivery.date(), cursor.date()) <= 1: order["eta_risk"] = "At Risk"
        else: order["eta_risk"] = "On Track"
