import frappe
from frappe.model.document import Document
from frappe.utils import flt


class FactoryWorkerCostRate(Document):
    def validate(self):
        if self.user == "Guest":
            frappe.throw("Guest cannot be used as a factory worker")
        if flt(self.hourly_cost) < 0:
            frappe.throw("Hourly Labor Cost cannot be negative")
        if not frappe.db.exists("User", self.user):
            frappe.throw(f"User {self.user} does not exist")
        if not self.currency and self.company:
            self.currency = frappe.db.get_value("Company", self.company, "default_currency")
