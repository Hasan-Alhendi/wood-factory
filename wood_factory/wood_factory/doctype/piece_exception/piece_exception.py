import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class PieceException(Document):
    def before_insert(self):
        piece = frappe.get_doc("Factory Piece", self.factory_piece)
        if piece.is_exception: frappe.throw(f"Piece {piece.name} is already tracked separately")
        if frappe.db.exists("Piece Exception", {"factory_piece": piece.name, "status": ["not in", ["Resolved", "Cancelled"]]}): frappe.throw(f"An open exception already exists for piece {piece.name}")
        self.factory_order = piece.factory_order; self.reported_stage = piece.current_stage; self.reported_by = frappe.session.user; self.reported_at = now_datetime()

    def after_insert(self): frappe.get_doc("Factory Piece", self.factory_piece).track_separately(f"{self.exception_type}: {self.reason}")

    @frappe.whitelist()
    def require_replacement(self):
        if self.status in ("Resolved", "Cancelled"): frappe.throw("Closed exception cannot require replacement")
        self.status = "Replacement Required"; self.save(); return self._summary()

    @frappe.whitelist()
    def start_replacement(self):
        if self.status != "Replacement Required": frappe.throw("Mark the exception as Replacement Required first")
        if self.replacement_piece: frappe.throw(f"Replacement piece {self.replacement_piece} already exists")
        original = frappe.get_doc("Factory Piece", self.factory_piece); replacement = frappe.copy_doc(original)
        replacement.name = None; replacement.piece_uid = f"{original.piece_uid}-R{self._replacement_number(original.name)}"; replacement.source_piece_id = original.source_piece_id
        replacement.is_exception = 1; replacement.exception_reason = f"Replacement for {original.name} / {self.name}"; replacement.current_stage = "Cutting"; replacement.status = "Ready"
        replacement.responsible = self.responsible or frappe.session.user; replacement.stage_started_at = None; replacement.blocked_at = None; replacement.blocked_minutes = 0; replacement.block_reason = None; replacement.completed_at = None
        replacement.insert(ignore_permissions=True); self.replacement_piece = replacement.name; self.replacement_started_at = now_datetime(); self.status = "Replacement In Production"; self.save(); return self._summary()

    @frappe.whitelist()
    def find_best_remnant(self):
        if not self.replacement_piece: frappe.throw("Start replacement manufacturing first")
        piece = frappe.get_doc("Factory Piece", self.replacement_piece); required_board_item = frappe.db.get_value("Cutting Order", piece.cutting_order, "board_item")
        if not required_board_item: frappe.throw(f"Cannot determine required board item for {piece.name}")
        piece_area = flt(piece.width_mm) * flt(piece.height_mm) / 1_000_000
        candidates = frappe.get_all("Board Remnant", filters={"status": "Available", "board_item": required_board_item}, fields=["name", "width_mm", "height_mm", "area_m2", "warehouse"]); matches = []
        for remnant in candidates:
            normal = flt(piece.width_mm) <= flt(remnant.width_mm) and flt(piece.height_mm) <= flt(remnant.height_mm); rotated = flt(piece.height_mm) <= flt(remnant.width_mm) and flt(piece.width_mm) <= flt(remnant.height_mm)
            if normal or rotated: matches.append((flt(remnant.area_m2) - piece_area, flt(remnant.area_m2), remnant.name))
        if not matches:
            self.suggested_remnant = None; self.remnant_waste_area_m2 = 0; self.save(); return {"found": False, "board_item": required_board_item, "piece": piece.name}
        waste, _area, remnant_name = min(matches, key=lambda row: (row[0], row[1], row[2])); remnant = frappe.get_doc("Board Remnant", remnant_name); remnant.reserve_for_piece(piece.name)
        self.suggested_remnant = remnant.name; self.remnant_waste_area_m2 = flt(waste, 4); self.save(); return {"found": True, "board_item": required_board_item, "piece": piece.name, "remnant": remnant.name, "waste_area_m2": self.remnant_waste_area_m2}

    @frappe.whitelist()
    def create_replacement_cutting_order(self):
        if not self.replacement_piece: frappe.throw("Start replacement manufacturing first")
        if self.suggested_remnant: frappe.throw(f"Remnant {self.suggested_remnant} is already reserved for this replacement")
        if self.replacement_cutting_order: frappe.throw(f"Replacement Cutting Order {self.replacement_cutting_order} already exists")
        piece = frappe.get_doc("Factory Piece", self.replacement_piece); source = frappe.get_doc("Cutting Order", piece.cutting_order)
        cutting = frappe.new_doc("Cutting Order")
        cutting.update({"factory_order": self.factory_order, "order_type": "Internal Replacement", "piece_exception": self.name, "customer_billable": 0, "board_item": source.board_item, "board_warehouse": source.board_warehouse, "edge_band_warehouse": source.edge_band_warehouse, "board_width_mm": source.board_width_mm, "board_height_mm": source.board_height_mm, "saw_kerf_mm": source.saw_kerf_mm, "algorithm": "Auto", "status": "Draft"})
        source_row = next((row for row in source.parts or [] if int(row.idx) == int(piece.source_piece_id.split("-")[0].replace("R", ""))), None)
        cutting.append("parts", {"part_name": piece.part_name, "width_mm": piece.width_mm, "height_mm": piece.height_mm, "qty": 1, "allow_rotation": source_row.allow_rotation if source_row else 1, "grain_direction": source_row.grain_direction if source_row else "Any", "edge_top": source_row.edge_top if source_row else 0, "edge_right": source_row.edge_right if source_row else 0, "edge_bottom": source_row.edge_bottom if source_row else 0, "edge_left": source_row.edge_left if source_row else 0, "edge_band_item": source_row.edge_band_item if source_row else None, "edge_band_rate_per_m": source_row.edge_band_rate_per_m if source_row else 0, "notes": f"Factory-funded replacement for {piece.name}; customer is not billed"})
        cutting.insert(ignore_permissions=True); self.replacement_cutting_order = cutting.name; self.save(); return {"cutting_order": cutting.name, "customer_billable": False, "factory_order": self.factory_order, "replacement_piece": piece.name}

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
        if self.replacement_piece: original.status = "Completed"; original.current_stage = "Completed"; original.completed_at = now_datetime(); original.save()
        else: original.return_to_order_flow()
        self.status = "Resolved"; self.resolution_notes = resolution_notes; self.resolved_at = now_datetime(); self.save(); return self._summary()

    @frappe.whitelist()
    def cancel_exception(self, resolution_notes):
        if self.status in ("Resolved", "Cancelled"): frappe.throw("Exception is already closed")
        if self.replacement_piece: frappe.throw("Cannot cancel an exception after replacement manufacturing has started")
        if not resolution_notes: frappe.throw("Cancellation notes are required")
        frappe.get_doc("Factory Piece", self.factory_piece).return_to_order_flow(); self.status = "Cancelled"; self.resolution_notes = resolution_notes; self.resolved_at = now_datetime(); self.save(); return self._summary()

    @staticmethod
    def _replacement_number(piece_name): return frappe.db.count("Piece Exception", {"factory_piece": piece_name, "replacement_piece": ["is", "set"]}) + 1

    def _summary(self): return {"name": self.name, "factory_piece": self.factory_piece, "factory_order": self.factory_order, "exception_type": self.exception_type, "status": self.status, "replacement_piece": self.replacement_piece, "suggested_remnant": self.suggested_remnant, "replacement_cutting_order": self.replacement_cutting_order}
