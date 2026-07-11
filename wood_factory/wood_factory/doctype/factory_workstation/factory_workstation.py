import frappe
from frappe.model.document import Document
from frappe.utils import flt


class FactoryWorkstation(Document):
    def validate(self):
        if self.minutes_per_day <= 0:
            frappe.throw("Capacity Minutes / Day must be greater than zero")
        if not 0 < flt(self.efficiency_percent) <= 100:
            frappe.throw("Efficiency Percent must be greater than 0 and not exceed 100")
        if self.status != "Active" and not self.unavailable_reason:
            frappe.throw("Unavailable Reason is required when workstation is not active")
        self.effective_minutes_per_day = flt(self.minutes_per_day * flt(self.efficiency_percent) / 100, 2) if self.status == "Active" else 0
