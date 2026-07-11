import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class PieceException(Document):
    def before_insert(self):
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        if piece.is_exception: frappe.throw(f"Piece {piece.name} is already tracked separately")
        if frappe.db.exists("Piece Exception", {"factory_piece": piece.name, "status": ["not in", ["Resolved", "Cancelled"]]}): frappe.throw(f"An open exception already exists for piece {piece.name}")
        self.factory_order = piece.factory_order; self.reported_stage = piece.current_stage; self.reported_by = frappe.session.user; self.reported_at = now_datetime()

    def after_insert(self):
        frappe.get_doc("Factory Piece", self.factory_piece).track_separately(f"{self.exception_type}: {self.reason}")

    @frappe.whitelist()
    def require_replacement(self):
        if self.status in ("Resolved", "Cancelled"): frappe.throw("Closed exception cannot require replacement")
        self.status = "Replacement Required"; self.save(); return self._summary()

    @frappe.whitelist()
    def start_replacement(self):
        if self.status != "Replacement Required": frappe.throw("Mark the exception as Replacement Required first")
        if self.replacement_piece: frappe.throw(f"Replacement piece {self.replacement_piece} already exists")
        original = frappe.get_doc("Factory Piece", self.factory_piece)
        replacement = frappe.copy_doc(original)
        replacement.name = None
        replacement.piece_uid = f"{original.piece_uid}-R{self._replacement_number(original.name)}"
        replacement.source_piece_id = original.source_piece_id
        replacement.is_exception = 1
        replacement.exception_reason = f"Replacement for {original.name} / {self.name}"
        replacement.current_stage = "Cutting"; replacement.status = "Ready"
        replacement.responsible = self.responsible or frappe.session.user
        replacement.stage_started_at = None; replacement.blocked_at = None; replacement.blocked_minutes = 0; replacement.block_reason = None; replacement.completed_at = None
        replacement.insert(ignore_permissions=True)
        self.replacement_piece = replacement.name
        self.replacement_started_at = now_datetime()
        self.status = "Replacement In Production"
        self.save()
        return self._summary()

    @frappe.whitelist()
    def find_best_remnant(self):
        if not self.replacement_piece:
            frappe.throw("Start replacement manufacturing first")
        piece = frappe.get_doc("Factory Piece", self.replacement_piece)
        required_board_item = frappe.db.get_value("Cutting Order", piece.cutting_order, "board_item")
        if not required_board_item:
            frappe.throw(f"Cannot determine required board item for {piece.name}")
        piece_area = flt(piece.width_mm) * flt(piece.height_mm) / 1_000_000
        candidates = frappe.get_all("Board Remnant", filters={"status": "Available", "board_item": required_board_item}, fields=["name", "width_mm", "height_mm", "area_m2", "warehouse"])
        matches = []
        for remnant in candidates:
            normal = flt(piece.width_mm) <= flt(remnant.width_mm) and flt(piece.height_mm) <= flt(remnant.height_mm)
            rotated = flt(piece.height_mm) <= flt(remnant.width_mm) and flt(piece.width_mm) <= flt(remnant.height_mm)
            if normal or rotated:
                matches.append((flt(remnant.area_m2) - piece_area, flt(remnant.area_m2), remnant.name))
        if not matches:
            self.suggested_remnant = None; self.remnant_waste_area_m2 = 0; self.save()
            return {"found": False, "board_item": required_board_item, "piece": piece.name}
        waste, _area, remnant_name = min(matches, key=lambda row: (row[0], row[1], row[2]))
        remnant = frappe.get_doc("Board Remnant", remnant_name)
        remnant.reserve_for_piece(piece.name)
        self.suggested_remnant = remnant.name
        self.remnant_waste_area_m2 = flt(waste, 4)
        self.save()
        return {"found": True, "board_item": required_board_item, "piece": piece.name, "remnant": remnant.name, "waste_area_m2": self.remnant_waste_area_m2}

    @frappe.whitelist()
    def confirm_replacement_completed(self):
        if self.status != "Replacement In Production" or not self.replacement_piece: frappe.throw("No replacement piece is currently in production")
        replacement = frappe.get_doc("Factory Piece", self.replacement_piece)
        if replacement.status != "Completed" or replacement.current_stage != "Completed": frappe.throw("Replacement piece must complete its production stages first")
        self.status = "Replacement Completed"; self.replacement_completed_at = now_datetime(); self.save(); return self._summary()

    @frappe.whitelist()
    def resolve(self, resolution_notes):
        if self.status in ("Resolved", "Cancelled"): frappe.throw("Exception is already closed")
        if not resolution_notes: frappe.throw("Resolution notes are required")
        if self.replacement_piece and self.status != "Replacement Completed": frappe.throw("Complete the replacement piece before resolving this exception")
        original = frappe.get_doc("Factory Piece", self.factory_piece)
        if self.replacement_piece:
            original.status = "Completed"; original.current_stage = "Completed"; original.completed_at = now_datetime(); original.save()
        else: original.return_to_order_flow()
        self.status = "Resolved"; self.resolution_notes = resolution_notes; self.resolved_at = now_datetime(); self.save(); return self._summary()

    @frappe.whitelist()
    def cancel_exception(self, resolution_notes):
        if self.status in ("Resolved", "Cancelled"): frappe.throw("Exception is already closed")
        if self.replacement_piece: frappe.throw("Cannot cancel an exception after replacement manufacturing has started")
        if not resolution_notes: frappe.throw("Cancellation notes are required")
        frappe.get_doc("Factory Piece", self.factory_piece).return_to_order_flow()
        self.status = "Cancelled"; self.resolution_notes = resolution_notes; self.resolved_at = now_datetime(); self.save(); return self._summary()

    @staticmethod
    def _replacement_number(piece_name):
        return frappe.db.count("Piece Exception", {"factory_piece": piece_name, "replacement_piece": ["is", "set"]}) + 1

    def _summary(self):
        return {"name": self.name, "factory_piece": self.factory_piece, "factory_order": self.factory_order, "exception_type": self.exception_type, "status": self.status, "replacement_piece": self.replacement_piece, "suggested_remnant": self.suggested_remnant}
