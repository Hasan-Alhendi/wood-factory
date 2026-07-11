import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, flt, now_datetime, nowdate, time_diff_in_seconds


class FactoryOrder(Document):
    def validate(self):
        self._validate_dates()
        self._set_delay()
        self._sync_execution_state()

    def _validate_dates(self):
        if self.expected_delivery_date and self.order_date and date_diff(self.expected_delivery_date, self.order_date) < 0:
            frappe.throw("Expected delivery date cannot be before order date")

    def _set_delay(self):
        if not self.expected_delivery_date or self.status in ("Delivered", "Closed", "Cancelled"):
            self.delay_days = 0
            return
        self.delay_days = max(date_diff(nowdate(), self.expected_delivery_date), 0)

    def _sync_execution_state(self):
        stages = list(self.production_stages or [])
        if not stages:
            self.progress_percent = 0
            self.current_stage = None
            self.current_responsible = None
            return
        completed = sum(1 for row in stages if row.status in ("Completed", "Skipped"))
        self.progress_percent = flt((completed / len(stages)) * 100, 2)
        current = next((row for row in stages if row.status in ("In Progress", "Blocked")), None)
        if not current:
            current = next((row for row in stages if row.status == "Ready"), None)
        self.current_stage = current.stage if current else None
        self.current_responsible = current.responsible if current else None
        if all(row.status in ("Completed", "Skipped") for row in stages):
            self.status = "Quality Inspection"
        elif any(row.status in ("In Progress", "Blocked") for row in stages):
            self.status = "In Production"

    @frappe.whitelist()
    def initialize_production_stages(self):
        if self.production_stages:
            frappe.throw("Production stages already exist")
        for index, stage in enumerate(("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")):
            self.append("production_stages", {"stage": stage, "status": "Ready" if index == 0 else "Pending"})
        self.save()
        return self._execution_summary()

    @frappe.whitelist()
    def start_stage(self, row_name):
        row = self._stage(row_name)
        if row.status not in ("Ready", "Blocked"):
            frappe.throw("Only a ready or blocked stage can be started")
        active = next((stage for stage in self.production_stages if stage.name != row.name and stage.status == "In Progress"), None)
        if active:
            frappe.throw(f"Stage {active.stage} is already in progress")
        now = now_datetime()
        if row.status == "Blocked" and row.blocked_at:
            row.blocked_minutes = flt(row.blocked_minutes) + (time_diff_in_seconds(now, row.blocked_at) / 60)
            row.blocked_at = None
        if not row.started_at:
            row.started_at = now
        row.status = "In Progress"
        self.save()
        return self._execution_summary()

    @frappe.whitelist()
    def block_stage(self, row_name, reason):
        row = self._stage(row_name)
        if row.status != "In Progress":
            frappe.throw("Only an in-progress stage can be blocked")
        if not reason:
            frappe.throw("Block reason is required")
        row.status = "Blocked"
        row.block_reason = reason
        row.blocked_at = now_datetime()
        self.save()
        return self._execution_summary()

    @frappe.whitelist()
    def complete_stage(self, row_name):
        row = self._stage(row_name)
        if row.status != "In Progress":
            frappe.throw("Only an in-progress stage can be completed")
        now = now_datetime()
        row.completed_at = now
        elapsed = time_diff_in_seconds(now, row.started_at) / 60 if row.started_at else 0
        row.actual_minutes = flt(max(elapsed - flt(row.blocked_minutes), 0), 2)
        row.status = "Completed"
        row.blocked_at = None
        next_row = next((stage for stage in self.production_stages if stage.idx > row.idx and stage.status == "Pending"), None)
        if next_row:
            next_row.status = "Ready"
        self.save()
        return self._execution_summary()

    def _stage(self, row_name):
        row = next((stage for stage in self.production_stages if stage.name == row_name), None)
        if not row:
            frappe.throw("Production stage not found")
        return row

    def _execution_summary(self):
        return {"status": self.status, "current_stage": self.current_stage, "current_responsible": self.current_responsible, "progress_percent": self.progress_percent}
