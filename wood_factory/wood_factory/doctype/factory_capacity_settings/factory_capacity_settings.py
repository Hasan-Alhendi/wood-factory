import frappe
from frappe.model.document import Document


class FactoryCapacitySettings(Document):
    def validate(self):
        if self.planning_days < 1:
            frappe.throw("Planning Horizon Days must be at least 1")
        for field in (
            "cutting_minutes_per_day", "edge_banding_minutes_per_day", "drilling_minutes_per_day",
            "assembly_minutes_per_day", "quality_inspection_minutes_per_day", "packing_minutes_per_day",
        ):
            if self.get(field) <= 0:
                frappe.throw(f"{self.meta.get_label(field)} must be greater than zero")
