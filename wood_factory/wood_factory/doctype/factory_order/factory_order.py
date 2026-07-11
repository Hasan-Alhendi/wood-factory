import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, flt, nowdate


class FactoryOrder(Document):
    def validate(self):
        self._validate_dates()
        self._set_delay()
        self._set_progress()

    def _validate_dates(self):
        if self.expected_delivery_date and self.order_date:
            if date_diff(self.expected_delivery_date, self.order_date) < 0:
                frappe.throw("Expected delivery date cannot be before order date")

    def _set_delay(self):
        if not self.expected_delivery_date or self.status in ("Delivered", "Closed", "Cancelled"):
            self.delay_days = 0
            return
        self.delay_days = max(date_diff(nowdate(), self.expected_delivery_date), 0)

    def _set_progress(self):
        stages = list(self.production_stages or [])
        if not stages:
            self.progress_percent = 0
            return
        completed = sum(1 for row in stages if row.status == "Completed")
        self.progress_percent = flt((completed / len(stages)) * 100, 2)
