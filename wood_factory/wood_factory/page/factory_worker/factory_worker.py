import frappe
from frappe.utils import date_diff, getdate, nowdate


STAGES = ["Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing"]
PRIORITY_WEIGHT = {"Urgent": 4000, "High": 3000, "Normal": 2000, "Low": 1000}


@frappe.whitelist()
def get_worker_queue(stage=None, workstation=None):
    user = frappe.session.user
    stage = frappe.db.get_value("Factory Workstation", workstation, "stage") if workstation else stage
    order_filters = {
        "status": ["not in", ["New", "Confirmed", "Waiting for Materials", "Delivered", "Closed", "Cancelled"]],
        "current_stage": ["is", "set"],
    }
    if stage:
        order_filters["current_stage"] = stage
    orders = frappe.get_all("Factory Order", filters=order_filters, fields=["name", "customer", "current_stage", "status", "priority", "progress_percent", "expected_delivery_date", "delay_days", "current_responsible", "modified"])
    exception_counts = dict(frappe.db.sql("""select factory_order, count(*) from `tabPiece Exception` where status not in ('Resolved','Cancelled') group by factory_order"""))
    today = getdate(nowdate())
    queued_orders = []
    for order in orders:
        assignment = frappe.db.get_value("Factory Order Stage", {"parent": order.name, "stage": order.current_stage, "status": ["in", ["Ready", "In Progress", "Blocked"]]}, ["name", "status", "workstation"], as_dict=True)
        if not assignment or (workstation and assignment.workstation != workstation):
            continue
        delivery = getdate(order.expected_delivery_date) if order.expected_delivery_date else None
        days_left = date_diff(delivery, today) if delivery else 999
        delayed = max(-days_left, 0) if delivery else order.delay_days or 0
        exceptions = exception_counts.get(order.name, 0)
        priority = order.priority or "Normal"
        score = PRIORITY_WEIGHT.get(priority, 2000) + min(delayed, 30) * 100 + exceptions * 75 - min(max(days_left, 0), 90)
        order.update({"stage_status": assignment.status, "workstation": assignment.workstation, "days_left": days_left if delivery else None, "open_exceptions": exceptions, "queue_score": score})
        queued_orders.append(order)
    queued_orders.sort(key=lambda row: (-row.queue_score, row.expected_delivery_date or "9999-12-31", row.modified))
    for position, order in enumerate(queued_orders, 1):
        order["queue_position"] = position
    exceptions = frappe.get_all("Factory Piece", filters={"is_exception": 1, "status": ["not in", ["Completed", "Cancelled"]], **({"current_stage": stage} if stage else {})}, fields=["name", "piece_uid", "factory_order", "part_name", "width_mm", "height_mm", "current_stage", "status", "block_reason", "responsible"], order_by="modified asc")
    workstations = frappe.get_all("Factory Workstation", filters={"status": "Active", **({"stage": stage} if stage else {})}, fields=["name", "stage"], order_by="stage asc, name asc")
    return {"user": user, "stage": stage, "workstation": workstation, "orders": queued_orders, "exceptions": exceptions, "stages": STAGES, "workstations": workstations}


@frappe.whitelist()
def run_order_action(order, action, reason=None, workstation=None):
    doc = frappe.get_doc("Factory Order", order)
    row = next((stage for stage in doc.production_stages if stage.stage == doc.current_stage and stage.status in ("Ready", "In Progress", "Blocked")), None)
    if not row:
        frappe.throw("No active production stage found")
    if workstation and row.workstation != workstation:
        frappe.throw(f"Order {order} is assigned to {row.workstation or 'another queue'}, not {workstation}")
    if action == "start":
        return doc.start_stage(row.name)
    if action == "complete":
        return doc.complete_stage(row.name)
    if action == "block":
        return doc.block_stage(row.name, reason)
    frappe.throw("Unsupported worker action")


@frappe.whitelist()
def run_piece_action(piece, action, reason=None):
    doc = frappe.get_doc("Factory Piece", piece)
    if not doc.is_exception:
        frappe.throw("Normal pieces are controlled by the whole Factory Order")
    if action == "start":
        return doc.start_stage()
    if action == "complete":
        return doc.complete_stage()
    if action == "block":
        return doc.block_stage(reason)
    frappe.throw("Unsupported worker action")
