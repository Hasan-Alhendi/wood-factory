import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, time_diff_in_seconds


STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")


class FactoryPiece(Document):
    def _require_exception(self):
        if not self.is_exception:
            frappe.throw("This piece follows the Factory Order. Mark it for separate tracking only when it is missing, damaged, or delayed.")

    @frappe.whitelist()
    def track_separately(self, reason):
        if self.is_exception:
            frappe.throw("Piece is already tracked separately")
        if not reason:
            frappe.throw("Separate tracking reason is required")
        self.is_exception = 1
        self.exception_reason = reason
        self.responsible = frappe.session.user
        self.save()
        return self._summary()

    @frappe.whitelist()
    def return_to_order_flow(self):
        self._require_exception()
        order = frappe.get_doc("Factory Order", self.factory_order)
        self.is_exception = 0
        self.exception_reason = None
        self.block_reason = None
        self.blocked_at = None
        self.blocked_minutes = 0
        self.current_stage = order.current_stage or "Cutting"
        active = next((row for row in order.production_stages if row.stage == self.current_stage), None)
        self.status = active.status if active and active.status in ("Ready", "In Progress") else "Ready"
        self.responsible = active.responsible if active else None
        self.stage_started_at = active.started_at if active else None
        self.save()
        return self._summary()

    @frappe.whitelist()
    def start_stage(self):
        self._require_exception()
        if self.status not in ("Ready", "Blocked") or self.current_stage == "Completed": frappe.throw("Piece is not ready to start")
        now = now_datetime()
        if self.status == "Blocked" and self.blocked_at:
            self.blocked_minutes = flt(self.blocked_minutes) + time_diff_in_seconds(now, self.blocked_at) / 60
            self.blocked_at = None
        self.status = "In Progress"; self.stage_started_at = self.stage_started_at or now; self.block_reason = None
        self.save(); return self._summary()

    @frappe.whitelist()
    def block_stage(self, reason):
        self._require_exception()
        if self.status != "In Progress": frappe.throw("Only an in-progress piece can be blocked")
        if not reason: frappe.throw("Block reason is required")
        self.status = "Blocked"; self.block_reason = reason; self.blocked_at = now_datetime()
        self.save(); return self._summary()

    @frappe.whitelist()
    def complete_stage(self):
        self._require_exception()
        if self.status != "In Progress": frappe.throw("Only an in-progress piece can complete a stage")
        try: index = STAGES.index(self.current_stage)
        except ValueError: frappe.throw("Invalid production stage")
        if index + 1 < len(STAGES):
            self.current_stage = STAGES[index + 1]; self.status = "Ready"; self.stage_started_at = None; self.blocked_at = None; self.blocked_minutes = 0; self.block_reason = None
        else:
            self.current_stage = "Completed"; self.status = "Completed"; self.completed_at = now_datetime()
        self.save(); return self._summary()

    def _summary(self):
        return {"piece_uid": self.piece_uid, "is_exception": self.is_exception, "current_stage": self.current_stage, "status": self.status, "responsible": self.responsible}
