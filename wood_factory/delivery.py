import frappe
from frappe.utils import now_datetime

from wood_factory.security import require_delivery


@frappe.whitelist()
def mark_ready_for_delivery(factory_order):
    require_delivery()
    order = frappe.get_doc("Factory Order", factory_order)
    if order.status in ("Cancelled", "Closed", "Delivered"):
        frappe.throw(f"Factory Order {order.name} cannot be prepared for delivery from status {order.status}")
    incomplete = [row.stage for row in order.production_stages or [] if row.status not in ("Completed", "Skipped")]
    if incomplete:
        frappe.throw("Complete all production stages before delivery: " + ", ".join(incomplete))
    open_exceptions = frappe.db.count(
        "Piece Exception",
        {"factory_order": order.name, "status": ["not in", ["Resolved", "Cancelled"]]},
    )
    if open_exceptions:
        frappe.throw(f"Resolve {open_exceptions} open piece exception(s) before delivery")
    order.db_set({"status": "Ready for Delivery", "current_stage": None, "current_responsible": None})
    _record_delivery_event(order.name, "Ready for Delivery", "Order production and exception checks completed")
    return {"factory_order": order.name, "status": "Ready for Delivery"}


@frappe.whitelist()
def mark_delivered(factory_order):
    require_delivery()
    order = frappe.get_doc("Factory Order", factory_order)
    if order.status != "Ready for Delivery":
        frappe.throw("Only an order marked Ready for Delivery can be delivered")
    order.db_set({"status": "Delivered", "delay_days": 0})
    _record_delivery_event(order.name, "Delivered", f"Delivery confirmed by {frappe.session.user}")
    return {"factory_order": order.name, "status": "Delivered", "delivered_at": now_datetime()}


def _record_delivery_event(factory_order, event_type, details):
    event = frappe.new_doc("Factory Order Event")
    event.update({
        "factory_order": factory_order,
        "event_type": event_type,
        "event_at": now_datetime(),
        "performed_by": frappe.session.user,
        "details": details,
        "reference_doctype": "Factory Order",
        "reference_name": factory_order,
    })
    event.flags.factory_event_insert = True
    event.insert(ignore_permissions=True)
