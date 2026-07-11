import frappe


@frappe.whitelist()
def get_order_timeline(factory_order):
    order = frappe.get_doc("Factory Order", factory_order)
    events = frappe.get_all(
        "Factory Order Event",
        filters={"factory_order": factory_order},
        fields=["name", "event_type", "stage", "event_at", "performed_by", "reason", "details", "reference_doctype", "reference_name"],
        order_by="event_at asc, creation asc",
    )
    return {
        "order": {"name": order.name, "customer": order.customer, "status": order.status, "current_stage": order.current_stage, "progress_percent": order.progress_percent},
        "events": events,
    }
