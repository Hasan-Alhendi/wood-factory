import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CuttingOrder(Document):
    def validate(self):
        self._validate_board()
        self._validate_parts()
        self._calculate_totals()

    def _validate_board(self):
        if flt(self.board_width_mm) <= 0 or flt(self.board_height_mm) <= 0:
            frappe.throw("Board width and height must be greater than zero")
        if flt(self.saw_kerf_mm) < 0:
            frappe.throw("Saw kerf cannot be negative")

    def _validate_parts(self):
        for row in self.parts or []:
            if flt(row.width_mm) <= 0 or flt(row.height_mm) <= 0 or row.qty <= 0:
                frappe.throw(f"Invalid dimensions or quantity in row {row.idx}")
            if not row.allow_rotation and (
                flt(row.width_mm) > flt(self.board_width_mm)
                or flt(row.height_mm) > flt(self.board_height_mm)
            ):
                frappe.throw(f"Part in row {row.idx} does not fit the selected board")
            if row.allow_rotation and min(flt(row.width_mm), flt(row.height_mm)) > min(flt(self.board_width_mm), flt(self.board_height_mm)):
                frappe.throw(f"Part in row {row.idx} does not fit the selected board")

    def _calculate_totals(self):
        self.total_pieces = sum(int(row.qty or 0) for row in self.parts or [])
        self.total_parts_area_m2 = flt(sum(flt(row.width_mm) * flt(row.height_mm) * int(row.qty or 0) for row in self.parts or []) / 1_000_000, 4)
