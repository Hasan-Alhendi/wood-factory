import frappe
from frappe.model.document import Document
from frappe.utils import flt

from wood_factory.wood_factory.cutting import optimize


class CuttingOrder(Document):
    def validate(self):
        self._validate_board(); self._validate_parts(); self._validate_order_type(); self._calculate_totals()

    def _validate_board(self):
        if flt(self.board_width_mm) <= 0 or flt(self.board_height_mm) <= 0: frappe.throw("Board width and height must be greater than zero")
        if flt(self.saw_kerf_mm) < 0: frappe.throw("Saw kerf cannot be negative")

    def _validate_order_type(self):
        if self.order_type == "Internal Replacement":
            if not self.piece_exception: frappe.throw("Internal replacement cutting requires a Piece Exception")
            self.customer_billable = 0
        else:
            self.customer_billable = 1

    def _validate_parts(self):
        for row in self.parts or []:
            if flt(row.width_mm) <= 0 or flt(row.height_mm) <= 0 or row.qty <= 0: frappe.throw(f"Invalid dimensions or quantity in row {row.idx}")
            orientations = [(flt(row.width_mm), flt(row.height_mm))]
            if row.allow_rotation and (row.grain_direction or "Any") == "Any": orientations.append((flt(row.height_mm), flt(row.width_mm)))
            if not any(width <= flt(self.board_width_mm) and height <= flt(self.board_height_mm) for width, height in orientations): frappe.throw(f"Part in row {row.idx} does not fit the selected board")
            if (row.edge_top or row.edge_right or row.edge_bottom or row.edge_left) and not row.edge_band_item: frappe.throw(f"Select an Edge Band Item in row {row.idx}")

    def _calculate_totals(self):
        self.total_pieces = sum(int(row.qty or 0) for row in self.parts or [])
        self.total_parts_area_m2 = flt(sum(flt(row.width_mm) * flt(row.height_mm) * int(row.qty or 0) for row in self.parts or []) / 1_000_000, 4)
        total_edge_length = total_edge_cost = 0
        for row in self.parts or []:
            width_edges = int(bool(row.edge_top)) + int(bool(row.edge_bottom)); height_edges = int(bool(row.edge_left)) + int(bool(row.edge_right))
            row.edge_band_length_m = flt(((flt(row.width_mm) * width_edges) + (flt(row.height_mm) * height_edges)) * int(row.qty or 0) / 1000, 3)
            row.edge_band_cost = flt(row.edge_band_length_m * flt(row.edge_band_rate_per_m), 2)
            total_edge_length += row.edge_band_length_m; total_edge_cost += row.edge_band_cost
        self.total_edge_band_length_m = flt(total_edge_length, 3); self.total_edge_band_cost = flt(total_edge_cost, 2); self.cutting_cost_usd = flt(self.board_count)

    @frappe.whitelist()
    def optimize_layout(self):
        if self.is_new(): frappe.throw("Save the Cutting Order before optimization")
        pieces = self._expand_pieces()
        if not pieces: frappe.throw("Add at least one door or part before optimization")
        try: result = optimize(flt(self.board_width_mm), flt(self.board_height_mm), pieces, flt(self.saw_kerf_mm), self.algorithm)
        except ValueError as exc: frappe.throw(str(exc))
        self._replace_layouts(result)
        board_count = len(result["boards"])
        self.db_set({"algorithm": result["algorithm"], "board_count": board_count, "waste_percent": result["waste_percent"], "cutting_cost_usd": board_count, "status": "Optimized"})
        return {"algorithm": result["algorithm"], "board_count": board_count, "waste_percent": result["waste_percent"], "cutting_cost_usd": board_count}

    @frappe.whitelist()
    def check_material_availability(self):
        self._require_optimized(); requirements = self._material_requirements(); shortages = []
        for item in requirements:
            available = self._available_qty(item["item_code"], item["warehouse"]); item["available_qty"] = available; item["shortage_qty"] = max(flt(item["qty"] - available), 0)
            if item["shortage_qty"] > 0: shortages.append(item)
        return {"requirements": requirements, "has_shortage": bool(shortages), "shortages": shortages}

    @frappe.whitelist()
    def approve_and_consume_materials(self):
        self._require_optimized()
        if self.material_stock_entry: frappe.throw(f"Materials already consumed by Stock Entry {self.material_stock_entry}")
        availability = self.check_material_availability()
        if availability["has_shortage"]:
            lines = [f'{row["item_code"]}: need {row["qty"]}, available {row["available_qty"]} in {row["warehouse"]}' for row in availability["shortages"]]
            frappe.throw("Insufficient material stock:<br>" + "<br>".join(lines))
        stock_entry = frappe.new_doc("Stock Entry"); stock_entry.stock_entry_type = "Material Issue"
        cost_owner = "factory" if self.order_type == "Internal Replacement" else f"customer order {self.factory_order}"
        stock_entry.remarks = f"Materials consumed for Cutting Order {self.name}; cost owner: {cost_owner}; Factory Order {self.factory_order}"
        for row in availability["requirements"]: stock_entry.append("items", {"item_code": row["item_code"], "s_warehouse": row["warehouse"], "qty": row["qty"], "uom": row["uom"], "stock_uom": row["uom"], "conversion_factor": 1})
        stock_entry.insert(ignore_permissions=True); stock_entry.submit(); self._create_factory_pieces()
        if self.order_type == "Internal Replacement": self._register_reusable_remnants()
        self.db_set({"material_stock_entry": stock_entry.name, "status": "Approved"})
        return {"stock_entry": stock_entry.name, "status": "Approved", "piece_count": frappe.db.count("Factory Piece", {"cutting_order": self.name})}

    def _create_factory_pieces(self):
        if self.order_type == "Internal Replacement": return
        if frappe.db.exists("Factory Piece", {"cutting_order": self.name}): frappe.throw("Factory pieces already exist for this Cutting Order")
        layouts = frappe.get_all("Board Layout", filters={"cutting_order": self.name}, fields=["name", "board_no"], order_by="board_no asc")
        for layout_row in layouts:
            layout = frappe.get_doc("Board Layout", layout_row.name)
            for placement in layout.placements or []:
                piece = frappe.new_doc("Factory Piece")
                piece.update({"piece_uid": f"{self.name}-{placement.piece_id}", "factory_order": self.factory_order, "cutting_order": self.name, "board_layout": layout.name, "board_no": layout.board_no, "source_piece_id": placement.piece_id, "part_name": placement.part_name, "width_mm": placement.width_mm, "height_mm": placement.height_mm, "current_stage": "Cutting", "status": "Ready"})
                piece.insert(ignore_permissions=True)

    def _register_reusable_remnants(self):
        result = optimize(flt(self.board_width_mm), flt(self.board_height_mm), self._expand_pieces(), flt(self.saw_kerf_mm), self.algorithm)
        layouts = frappe.get_all("Board Layout", filters={"cutting_order": self.name}, fields=["name", "board_no"], order_by="board_no asc")
        for index, board in enumerate(result["boards"]):
            layout_name = layouts[index].name if index < len(layouts) else None
            for rect in board.get("free_rectangles", []):
                if flt(rect["width"]) < 100 or flt(rect["height"]) < 100: continue
                remnant = frappe.new_doc("Board Remnant")
                remnant.update({"board_item": self.board_item, "warehouse": self.board_warehouse, "width_mm": rect["width"], "height_mm": rect["height"], "source_cutting_order": self.name, "source_board_layout": layout_name, "notes": f"Factory-owned leftover from internal replacement cutting {self.name}"})
                remnant.insert(ignore_permissions=True)

    def _require_optimized(self):
        if self.status not in ("Optimized", "Approved") or not self.board_count: frappe.throw("Optimize the Cutting Order before checking or consuming materials")
        if not self.board_warehouse: frappe.throw("Select the Board Warehouse")

    def _material_requirements(self):
        requirements = [{"item_code": self.board_item, "warehouse": self.board_warehouse, "qty": flt(self.board_count), "uom": frappe.db.get_value("Item", self.board_item, "stock_uom") or "Nos"}]; edge_items = {}
        for row in self.parts or []:
            if not row.edge_band_item or not flt(row.edge_band_length_m): continue
            warehouse = self.edge_band_warehouse or self.board_warehouse; key = (row.edge_band_item, warehouse); edge_items[key] = flt(edge_items.get(key)) + flt(row.edge_band_length_m)
        for (item_code, warehouse), qty in edge_items.items(): requirements.append({"item_code": item_code, "warehouse": warehouse, "qty": flt(qty, 3), "uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Meter"})
        return requirements

    @staticmethod
    def _available_qty(item_code, warehouse): return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))

    def _expand_pieces(self):
        pieces = []
        for row in self.parts or []:
            for piece_no in range(1, int(row.qty or 0) + 1): pieces.append({"piece_id": f"R{row.idx}-P{piece_no}", "source_row": row.idx, "part_name": row.part_name, "width": flt(row.width_mm), "height": flt(row.height_mm), "allow_rotation": bool(row.allow_rotation), "grain_direction": row.grain_direction or "Any", "edge_top": bool(row.edge_top), "edge_right": bool(row.edge_right), "edge_bottom": bool(row.edge_bottom), "edge_left": bool(row.edge_left)})
        return pieces

    def _replace_layouts(self, result):
        for name in frappe.get_all("Board Layout", filters={"cutting_order": self.name}, pluck="name"): frappe.delete_doc("Board Layout", name, ignore_permissions=True)
        for board_no, board in enumerate(result["boards"], 1):
            layout = frappe.new_doc("Board Layout"); layout.update({"cutting_order": self.name, "board_no": board_no, "board_item": self.board_item, "board_width_mm": self.board_width_mm, "board_height_mm": self.board_height_mm, "algorithm": result["algorithm"]})
            for placement in board["placements"]: layout.append("placements", {"piece_id": placement["piece_id"], "source_row": placement["source_row"], "part_name": placement["part_name"], "x_mm": placement["x"], "y_mm": placement["y"], "width_mm": placement["width"], "height_mm": placement["height"], "rotated": placement["rotated"], "edge_top": placement["edge_top"], "edge_right": placement["edge_right"], "edge_bottom": placement["edge_bottom"], "edge_left": placement["edge_left"]})
            layout.insert(ignore_permissions=True)