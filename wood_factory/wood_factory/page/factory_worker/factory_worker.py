import frappe


@frappe.whitelist()
def get_worker_queue(stage=None):
    user = frappe.session.user
    order_filters = {"status": ["not in", ["Delivered", "Closed", "Cancelled"]]}
    if stage:
        order_filters["current_stage"] = stage
    orders = frappe.get_all(
        "Factory Order",
        filters=order_filters,
        fields=["name", "customer", "current_stage", "status", "progress_percent", "expected_delivery_date", "delay_days", "current_responsible"],
        order_by="delay_days desc, expected_delivery_date asc, modified asc",
    )
    exceptions = frappe.get_all(
        "Factory Piece",
        filters={"is_exception": 1, "status": ["not in", ["Completed", "Cancelled"]], **({"current_stage": stage} if stage else {})},
        fields=["name", "piece_uid", "factory_order", "part_name", "width_mm", "height_mm", "current_stage", "status", "block_reason", "responsible"],
        order_by="modified asc",
    )
    return {
        "user": user,
        "stage": stage,
        "orders": orders,
        "exceptions": exceptions,
        "stages": ["Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing"],
    }


@frappe.whitelist()
def run_order_action(order, action, reason=None):
    doc = frappe.get_doc("Factory Order", order)
    row = next((stage for stage in doc.production_stages if stage.stage == doc.current_stage), None)
    if not row:
        frappe.throw("No active production stage found")
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
