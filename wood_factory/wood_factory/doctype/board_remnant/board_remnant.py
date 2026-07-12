import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


MIN_REMNANT_MM = 100


class BoardRemnant(Document):
    def validate(self):
        if flt(self.width_mm) <= 0 or flt(self.height_mm) <= 0:
            frappe.throw("Remnant width and height must be greater than zero")
        self.area_m2 = flt(flt(self.width_mm) * flt(self.height_mm) / 1_000_000, 4)
        if (self.source_cutting_order or self.parent_remnant) and not self.recovery_cost_ledger:
            from wood_factory.remnant_costing import calculate_remnant_value
            valuation = calculate_remnant_value(self)
            self.valuation_rate_per_m2 = valuation["rate_per_m2"]
            self.estimated_value = valuation["estimated_value"]
            self.currency = valuation["currency"]
        if self.status == "Available":
            self.reserved_for_piece = None
            self.reserved_at = None

    def after_insert(self):
        from wood_factory.remnant_costing import post_remnant_recovery
        ledger = post_remnant_recovery(self)
        if ledger:
            frappe.db.set_value("Board Remnant", self.name, "recovery_cost_ledger", ledger.name, update_modified=False)

    def on_trash(self):
        if flt(self.estimated_value) > 0 or self.recovery_cost_ledger or self.parent_remnant:
            frappe.throw("A valued remnant cannot be deleted. Mark it as Scrapped instead.")

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
            frappe.throw(f"Wrong board material/color. Piece {piece.name} requires {required_board_item}, but remnant {self.name} is {self.board_item}")
        if not self._fitting_orientations(piece):
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
        piece = frappe.get_doc("Factory Piece", self.reserved_for_piece)
        plan = self._best_cut_plan(piece)
        if not plan:
            frappe.throw(f"Piece {piece.name} no longer fits remnant {self.name}")

        rate = flt(self.valuation_rate_per_m2)
        consumed_area = flt(plan["occupied_width"] * plan["occupied_height"] / 1_000_000, 4)
        consumed_value = flt(consumed_area * rate, 2)
        child_docs = []
        child_value = 0
        for width, height in plan["children"]:
            child = frappe.new_doc("Board Remnant")
            child.update({
                "board_item": self.board_item,
                "warehouse": self.warehouse,
                "width_mm": width,
                "height_mm": height,
                "status": "Available",
                "source_cutting_order": self.source_cutting_order,
                "source_board_layout": self.source_board_layout,
                "parent_remnant": self.name,
                "notes": f"Reusable child remnant after cutting replacement piece {piece.name} from {self.name}",
            })
            child.insert(ignore_permissions=True)
            child_docs.append(child)
            child_value += flt(child.estimated_value)

        residual_scrap_value = flt(max(flt(self.estimated_value) - consumed_value - child_value, 0), 2)
        from wood_factory.remnant_costing import post_remnant_consumption, post_remnant_scrap_loss
        ledger = post_remnant_consumption(self, piece, consumed_value)
        post_remnant_scrap_loss(self, residual_scrap_value, factory_piece=piece.name, reason="Unusable residual and saw kerf")

        self.status = "Consumed"
        self.consumed_at = now_datetime()
        self.consumed_area_m2 = consumed_area
        self.consumed_value = consumed_value
        self.residual_scrap_value = residual_scrap_value
        self.consumption_cost_ledger = ledger.name if ledger else None
        self.child_remnant_count = len(child_docs)
        self.save()
        return {**self._summary(), "child_remnants": [child.name for child in child_docs]}

    @frappe.whitelist()
    def scrap(self):
        if self.status not in ("Available", "Reserved"):
            frappe.throw("Only an available or reserved remnant can be scrapped")
        if self.status == "Reserved":
            frappe.throw("Release the reservation before scrapping this remnant")
        from wood_factory.remnant_costing import post_remnant_scrap_loss, reverse_remnant_recovery
        recovery_reversed = False if self.parent_remnant else reverse_remnant_recovery(self)
        if not recovery_reversed:
            post_remnant_scrap_loss(self, self.estimated_value, reason="Stored remnant scrapped")
        self.status = "Scrapped"
        self.residual_scrap_value = flt(self.estimated_value, 2)
        self.save()
        return self._summary()

    def _fitting_orientations(self, piece):
        orientations = []
        piece_width, piece_height = flt(piece.width_mm), flt(piece.height_mm)
        if piece_width <= flt(self.width_mm) and piece_height <= flt(self.height_mm):
            orientations.append((piece_width, piece_height, False))
        if piece_height <= flt(self.width_mm) and piece_width <= flt(self.height_mm) and piece_width != piece_height:
            orientations.append((piece_height, piece_width, True))
        return orientations

    def _best_cut_plan(self, piece):
        kerf = flt(frappe.db.get_value("Cutting Order", piece.cutting_order, "saw_kerf_mm")) or 3
        plans = []
        remnant_width, remnant_height = flt(self.width_mm), flt(self.height_mm)
        for piece_width, piece_height, rotated in self._fitting_orientations(piece):
            occupied_width = min(piece_width + kerf, remnant_width)
            occupied_height = min(piece_height + kerf, remnant_height)
            split_options = [
                [(remnant_width - occupied_width, remnant_height), (occupied_width, remnant_height - occupied_height)],
                [(remnant_width, remnant_height - occupied_height), (remnant_width - occupied_width, occupied_height)],
            ]
            for rectangles in split_options:
                usable = [(flt(width), flt(height)) for width, height in rectangles if width >= MIN_REMNANT_MM and height >= MIN_REMNANT_MM]
                usable_area = sum(width * height for width, height in usable)
                largest_area = max([width * height for width, height in usable] or [0])
                residual = remnant_width * remnant_height - occupied_width * occupied_height - usable_area
                plans.append({
                    "rotated": rotated,
                    "occupied_width": occupied_width,
                    "occupied_height": occupied_height,
                    "children": usable,
                    "score": (-usable_area, residual, -largest_area, int(rotated)),
                })
        return min(plans, key=lambda row: row["score"]) if plans else None

    def _summary(self):
        return {
            "name": self.name,
            "board_item": self.board_item,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "area_m2": self.area_m2,
            "estimated_value": self.estimated_value,
            "currency": self.currency,
            "status": self.status,
            "parent_remnant": self.parent_remnant,
            "reserved_for_piece": self.reserved_for_piece,
            "consumed_area_m2": self.consumed_area_m2,
            "consumed_value": self.consumed_value,
            "residual_scrap_value": self.residual_scrap_value,
            "child_remnant_count": self.child_remnant_count,
            "recovery_cost_ledger": self.recovery_cost_ledger,
            "consumption_cost_ledger": self.consumption_cost_ledger,
        }
