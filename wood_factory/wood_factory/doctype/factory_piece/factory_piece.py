import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, time_diff_in_seconds


STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")


class FactoryPiece(Document):
    @frappe.whitelist()
    def start_stage(self):
        if self.status not in ("Ready", "Blocked") or self.current_stage == "Completed":
            frappe.throw("Piece is not ready to start")
        now = now_datetime()
        if self.status == "Blocked" and self.blocked_at:
            self.blocked_minutes = flt(self.blocked_minutes) + time_diff_in_seconds(now, self.blocked_at) / 60
            self.blocked_at = None
        self.status = "In Progress"
        self.stage_started_at = self.stage_started_at or now
        self.block_reason = None
        self.save()
        return self._summary()

    @frappe.whitelist()
    def block_stage(self, reason):
        if self.status != "In Progress":
            frappe.throw("Only an in-progress piece can be blocked")
        if not reason:
            frappe.throw("Block reason is required")
        self.status = "Blocked"
        self.block_reason = reason
        self.blocked_at = now_datetime()
        self.save()
        return self._summary()

    @frappe.whitelist()
    def complete_stage(self):
        if self.status != "In Progress":
            frappe.throw("Only an in-progress piece can complete a stage")
        try:
            index = STAGES.index(self.current_stage)
        except ValueError:
            frappe.throw("Invalid production stage")
        if index + 1 < len(STAGES):
            self.current_stage = STAGES[index + 1]
            self.status = "Ready"
            self.stage_started_at = None
            self.blocked_at = None
            self.blocked_minutes = 0
            self.block_reason = None
        else:
            self.current_stage = "Completed"
            self.status = "Completed"
            self.completed_at = now_datetime()
        self.save()
        return self._summary()

    def _summary(self):
        return {"piece_uid": self.piece_uid, "current_stage": self.current_stage, "status": self.status, "responsible": self.responsible}
