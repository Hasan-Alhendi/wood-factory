import frappe

from wood_factory.security import require_operational_view


@frappe.whitelist()
def get_order_timeline(factory_order):
    require_operational_view()
    order = frappe.get_doc("Factory Order", factory_order)
    if not frappe.has_permission("Factory Order", ptype="read", doc=order):
        frappe.throw("You are not permitted to view this Factory Order timeline", frappe.PermissionError)
    events = frappe.get_all(
        "Factory Order Event",
        filters={"factory_order": factory_order},
        fields=["name", "event_type", "stage", "event_at", "performed_by", "reason", "details", "reference_doctype", "reference_name"],
        order_by="event_at asc, creation asc",
        limit_page_length=0,
    )
    return {
        "order": {"name": order.name, "customer": order.customer, "status": order.status, "current_stage": order.current_stage, "progress_percent": order.progress_percent},
        "events": events,
    }
