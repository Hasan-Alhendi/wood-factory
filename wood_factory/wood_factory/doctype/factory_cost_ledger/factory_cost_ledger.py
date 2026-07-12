import frappe
from frappe.model.document import Document


class FactoryCostLedger(Document):
    def before_insert(self):
        if not getattr(self.flags, "factory_cost_insert", False):
            frappe.throw("Factory Cost Ledger entries are created automatically")

    def on_update(self):
        if not self.is_new() and not getattr(self.flags, "factory_cost_update", False):
            frappe.throw("Factory Cost Ledger entries cannot be edited manually")

    def on_trash(self):
        frappe.throw("Factory Cost Ledger entries cannot be deleted")
