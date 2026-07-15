from frappe.model.document import Document
from frappe.utils import flt


class BoardLayout(Document):
    def validate(self):
        board_area = flt(self.board_width_mm) * flt(self.board_height_mm)
        used_area = sum(flt(row.width_mm) * flt(row.height_mm) for row in self.placements or [])
        self.used_area_m2 = flt(used_area / 1_000_000, 4)
        self.waste_percent = flt(((board_area - used_area) / board_area) * 100, 2) if board_area else 0
