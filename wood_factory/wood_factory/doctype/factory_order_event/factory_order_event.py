import frappe
from frappe.model.document import Document


class FactoryOrderEvent(Document):
    def before_insert(self):
        if not getattr(self.flags, "factory_event_insert", False):
            frappe.throw("Factory Order Events are created automatically by the production workflow")

    def on_update(self):
        if not self.is_new() and not getattr(self.flags, "factory_event_insert", False):
            frappe.throw("Factory Order Events cannot be edited")

    def on_trash(self):
        frappe.throw("Factory Order Events cannot be deleted")
