import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class BoardRemnant(Document):
    def validate(self):
        if flt(self.width_mm) <= 0 or flt(self.height_mm) <= 0:
            frappe.throw("Remnant width and height must be greater than zero")
        self.area_m2 = flt(flt(self.width_mm) * flt(self.height_mm) / 1_000_000, 4)
        if self.status == "Available":
            self.reserved_for_piece = None
            self.reserved_at = None

    @frappe.whitelist()
    def reserve_for_piece(self, factory_piece):
        if self.status != "Available":
            frappe.throw("Only an available remnant can be reserved")
        piece = frappe.get_doc("Factory Piece", factory_piece)
        if not piece.is_exception:
            frappe.throw("Remnants are reserved here for separately tracked replacement pieces")
        required_board_item = frappe.db.get_value("Cutting Order", piece.cutting_order, "board_item")
        if not required_board_item:
            frappe.throw(f"Cannot determine the required board item for piece {piece.name}")
        if self.board_item != required_board_item:
            frappe.throw(
                f"Wrong board material/color. Piece {piece.name} requires {required_board_item}, "
                f"but remnant {self.name} is {self.board_item}"
            )
        fits_normal = flt(piece.width_mm) <= flt(self.width_mm) and flt(piece.height_mm) <= flt(self.height_mm)
        fits_rotated = flt(piece.height_mm) <= flt(self.width_mm) and flt(piece.width_mm) <= flt(self.height_mm)
        if not (fits_normal or fits_rotated):
            frappe.throw(f"Piece {piece.name} does not fit this remnant")
        self.status = "Reserved"
        self.reserved_for_piece = piece.name
        self.reserved_at = now_datetime()
        self.save()
        return self._summary()

    @frappe.whitelist()
    def release_reservation(self):
        if self.status != "Reserved":
            frappe.throw("Only a reserved remnant can be released")
        self.status = "Available"
        self.reserved_for_piece = None
        self.reserved_at = None
        self.save()
        return self._summary()

    @frappe.whitelist()
    def consume(self):
        if self.status != "Reserved" or not self.reserved_for_piece:
            frappe.throw("Reserve the remnant for a piece before consuming it")
        self.status = "Consumed"
        self.consumed_at = now_datetime()
        self.save()
        return self._summary()

    @frappe.whitelist()
    def scrap(self):
        if self.status not in ("Available", "Reserved"):
            frappe.throw("Only an available or reserved remnant can be scrapped")
        if self.status == "Reserved":
            frappe.throw("Release the reservation before scrapping this remnant")
        self.status = "Scrapped"
        self.save()
        return self._summary()

    def _summary(self):
        return {"name": self.name, "board_item": self.board_item, "width_mm": self.width_mm, "height_mm": self.height_mm, "area_m2": self.area_m2, "status": self.status, "reserved_for_piece": self.reserved_for_piece}
