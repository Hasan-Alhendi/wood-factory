import frappe
from frappe.model.document import Document


class FactoryPieceStageCost(Document):
    def before_insert(self):
        if not getattr(self.flags, "factory_cost_insert", False):
            frappe.throw("Factory Piece Stage Cost records are created automatically")

    def on_update(self):
        if not self.is_new() and not getattr(self.flags, "factory_cost_update", False):
            frappe.throw("Factory Piece Stage Cost records cannot be edited manually")

    def on_trash(self):
        frappe.throw("Factory Piece Stage Cost records cannot be deleted")
