import frappe
from frappe.model.document import Document
from frappe.utils import flt

from wood_factory.wood_factory.cutting import optimize


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
            orientations = [(flt(row.width_mm), flt(row.height_mm))]
            if row.allow_rotation and (row.grain_direction or "Any") == "Any":
                orientations.append((flt(row.height_mm), flt(row.width_mm)))
            if not any(width <= flt(self.board_width_mm) and height <= flt(self.board_height_mm) for width, height in orientations):
                frappe.throw(f"Part in row {row.idx} does not fit the selected board")
            if (row.edge_top or row.edge_right or row.edge_bottom or row.edge_left) and not row.edge_band_item:
                frappe.throw(f"Select an Edge Band Item in row {row.idx}")

    def _calculate_totals(self):
        self.total_pieces = sum(int(row.qty or 0) for row in self.parts or [])
        self.total_parts_area_m2 = flt(sum(flt(row.width_mm) * flt(row.height_mm) * int(row.qty or 0) for row in self.parts or []) / 1_000_000, 4)
        total_edge_length = 0
        total_edge_cost = 0
        for row in self.parts or []:
            width_edges = int(bool(row.edge_top)) + int(bool(row.edge_bottom))
            height_edges = int(bool(row.edge_left)) + int(bool(row.edge_right))
            row.edge_band_length_m = flt(((flt(row.width_mm) * width_edges) + (flt(row.height_mm) * height_edges)) * int(row.qty or 0) / 1000, 3)
            row.edge_band_cost = flt(row.edge_band_length_m * flt(row.edge_band_rate_per_m), 2)
            total_edge_length += row.edge_band_length_m
            total_edge_cost += row.edge_band_cost
        self.total_edge_band_length_m = flt(total_edge_length, 3)
        self.total_edge_band_cost = flt(total_edge_cost, 2)
        self.cutting_cost_usd = flt(self.board_count) * 1.0

    @frappe.whitelist()
    def optimize_layout(self):
        if self.is_new():
            frappe.throw("Save the Cutting Order before optimization")
        pieces = self._expand_pieces()
        if not pieces:
            frappe.throw("Add at least one door or part before optimization")
        try:
            result = optimize(flt(self.board_width_mm), flt(self.board_height_mm), pieces, flt(self.saw_kerf_mm), self.algorithm)
        except ValueError as exc:
            frappe.throw(str(exc))
        self._replace_layouts(result)
        board_count = len(result["boards"])
        self.db_set({"algorithm": result["algorithm"], "board_count": board_count, "waste_percent": result["waste_percent"], "cutting_cost_usd": board_count * 1.0, "status": "Optimized"})
        return {"algorithm": result["algorithm"], "board_count": board_count, "waste_percent": result["waste_percent"], "cutting_cost_usd": board_count * 1.0}

    def _expand_pieces(self):
        pieces = []
        for row in self.parts or []:
            for piece_no in range(1, int(row.qty or 0) + 1):
                pieces.append({"piece_id": f"R{row.idx}-P{piece_no}", "source_row": row.idx, "part_name": row.part_name, "width": flt(row.width_mm), "height": flt(row.height_mm), "allow_rotation": bool(row.allow_rotation), "grain_direction": row.grain_direction or "Any"})
        return pieces

    def _replace_layouts(self, result):
        old_layouts = frappe.get_all("Board Layout", filters={"cutting_order": self.name}, pluck="name")
        for name in old_layouts:
            frappe.delete_doc("Board Layout", name, ignore_permissions=True)
        for board_no, board in enumerate(result["boards"], 1):
            layout = frappe.new_doc("Board Layout")
            layout.update({"cutting_order": self.name, "board_no": board_no, "board_item": self.board_item, "board_width_mm": self.board_width_mm, "board_height_mm": self.board_height_mm, "algorithm": result["algorithm"]})
            for placement in board["placements"]:
                layout.append("placements", {"piece_id": placement["piece_id"], "source_row": placement["source_row"], "part_name": placement["part_name"], "x_mm": placement["x"], "y_mm": placement["y"], "width_mm": placement["width"], "height_mm": placement["height"], "rotated": placement["rotated"]})
            layout.insert(ignore_permissions=True)
