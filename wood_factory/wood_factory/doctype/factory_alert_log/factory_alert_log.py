import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class FactoryAlertLog(Document):
    @frappe.whitelist()
    def acknowledge(self):
        if self.status == "Resolved":
            frappe.throw("Resolved alert cannot be acknowledged")
        self.db_set({"status": "Acknowledged", "acknowledged_at": now_datetime(), "acknowledged_by": frappe.session.user})
        return self._summary()

    @frappe.whitelist()
    def resolve_alert(self):
        if self.status == "Resolved":
            return self._summary()
        self.db_set({"status": "Resolved", "resolved_at": now_datetime()})
        frappe.db.set_value(
            "ToDo",
            {"reference_type": self.reference_doctype, "reference_name": self.reference_name, "status": "Open"},
            "status",
            "Closed",
            update_modified=False,
        )
        return self._summary()

    def _summary(self):
        return {"name": self.name, "status": self.status, "severity": self.severity, "reference_doctype": self.reference_doctype, "reference_name": self.reference_name}
