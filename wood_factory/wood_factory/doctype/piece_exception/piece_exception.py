import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PieceException(Document):
    def before_insert(self):
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        if piece.is_exception:
            frappe.throw(f"Piece {piece.name} is already tracked separately")
        if frappe.db.exists("Piece Exception", {"factory_piece": piece.name, "status": ["not in", ["Resolved", "Cancelled"]]}):
            frappe.throw(f"An open exception already exists for piece {piece.name}")
        self.factory_order = piece.factory_order
        self.reported_stage = piece.current_stage
        self.reported_by = frappe.session.user
        self.reported_at = now_datetime()

    def after_insert(self):
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        piece.track_separately(f"{self.exception_type}: {self.reason}")

    @frappe.whitelist()
    def require_replacement(self):
        if self.status in ("Resolved", "Cancelled"):
            frappe.throw("Closed exception cannot require replacement")
        self.status = "Replacement Required"
        self.save()
        return self._summary()

    @frappe.whitelist()
    def resolve(self, resolution_notes):
        if self.status in ("Resolved", "Cancelled"):
            frappe.throw("Exception is already closed")
        if not resolution_notes:
            frappe.throw("Resolution notes are required")
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        piece.return_to_order_flow()
        self.status = "Resolved"
        self.resolution_notes = resolution_notes
        self.resolved_at = now_datetime()
        self.save()
        return self._summary()

    @frappe.whitelist()
    def cancel_exception(self, resolution_notes):
        if self.status in ("Resolved", "Cancelled"):
            frappe.throw("Exception is already closed")
        if not resolution_notes:
            frappe.throw("Cancellation notes are required")
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        piece.return_to_order_flow()
        self.status = "Cancelled"
        self.resolution_notes = resolution_notes
        self.resolved_at = now_datetime()
        self.save()
        return self._summary()

    def _summary(self):
        return {"name": self.name, "factory_piece": self.factory_piece, "factory_order": self.factory_order, "exception_type": self.exception_type, "status": self.status}
