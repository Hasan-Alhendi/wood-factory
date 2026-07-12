import frappe
from frappe.model.document import Document
from frappe.utils import flt


class FactoryAlertSettings(Document):
    def validate(self):
        threshold_fields = (
            "blocked_alert_hours", "blocked_critical_hours", "exception_alert_hours",
            "exception_critical_hours", "workstation_alert_hours", "workstation_critical_hours",
            "high_escalation_hours", "critical_escalation_hours", "repeat_notification_hours",
        )
        for fieldname in threshold_fields:
            if flt(self.get(fieldname)) <= 0:
                frappe.throw(f"{self.meta.get_label(fieldname)} must be greater than zero")
        if flt(self.blocked_critical_hours) < flt(self.blocked_alert_hours):
            frappe.throw("Blocked critical threshold cannot be lower than the alert threshold")
        if flt(self.exception_critical_hours) < flt(self.exception_alert_hours):
            frappe.throw("Exception critical threshold cannot be lower than the alert threshold")
        if flt(self.workstation_critical_hours) < flt(self.workstation_alert_hours):
            frappe.throw("Workstation critical threshold cannot be lower than the alert threshold")
