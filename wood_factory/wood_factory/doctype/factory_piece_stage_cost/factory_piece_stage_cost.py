import frappe
from frappe.model.document import Document


class FactoryPieceStageCost(Document):
    def before_insert(self):
        if not getattr(self.flags, "factory_cost_insert", False):
            frappe.throw("Factory Piece Stage Cost records are created automatically")

    def on_update(self):
        automatic_insert = getattr(self.flags, "factory_cost_insert", False)
        automatic_update = getattr(self.flags, "factory_cost_update", False)
        if not self.is_new() and not automatic_insert and not automatic_update:
            frappe.throw("Factory Piece Stage Cost records cannot be edited manually")

    def on_trash(self):
        frappe.throw("Factory Piece Stage Cost records cannot be deleted")
