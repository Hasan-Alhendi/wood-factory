import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, time_diff_in_seconds


STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")


class FactoryPiece(Document):
    def _require_exception(self):
        if not self.is_exception:
            frappe.throw("This piece follows the Factory Order. Mark it for separate tracking only when it is missing, damaged, or delayed.")

    @frappe.whitelist()
    def track_separately(self, reason):
        if self.is_exception:
            frappe.throw("Piece is already tracked separately")
        if not reason:
            frappe.throw("Separate tracking reason is required")
        self.is_exception = 1
        self.exception_reason = reason
        self.responsible = frappe.session.user
        self.save()
        return self._summary()

    @frappe.whitelist()
    def return_to_order_flow(self):
        self._require_exception()
        order = frappe.get_doc("Factory Order", self.factory_order)
        self.is_exception = 0
        self.exception_reason = None
        self.block_reason = None
        self.blocked_at = None
        self.blocked_minutes = 0
        self.current_stage = order.current_stage or "Cutting"
        active = next((row for row in order.production_stages if row.stage == self.current_stage), None)
        self.status = active.status if active and active.status in ("Ready", "In Progress") else "Ready"
        self.responsible = active.responsible if active else None
        self.workstation = active.workstation if active else None
        self.stage_started_at = active.started_at if active else None
        self.save()
        return self._summary()

    @frappe.whitelist()
    def start_stage(self, workstation=None):
        self._require_exception()
        if self.status not in ("Ready", "Blocked") or self.current_stage == "Completed":
            frappe.throw("Piece is not ready to start")
        self.workstation = self._resolve_workstation(workstation)
        if self.current_stage == "Cutting":
            self._consume_reserved_remnant()
        now = now_datetime()
        if self.status == "Blocked" and self.blocked_at:
            self.blocked_minutes = flt(self.blocked_minutes) + time_diff_in_seconds(now, self.blocked_at) / 60
            self.blocked_at = None
        self.status = "In Progress"
        self.stage_started_at = self.stage_started_at or now
        self.block_reason = None
        self.responsible = frappe.session.user
        self.save()
        return self._summary()

    @frappe.whitelist()
    def block_stage(self, reason):
        self._require_exception()
        if self.status != "In Progress":
            frappe.throw("Only an in-progress piece can be blocked")
        if not reason:
            frappe.throw("Block reason is required")
        self.status = "Blocked"
        self.block_reason = reason
        self.blocked_at = now_datetime()
        self.save()
        return self._summary()

    @frappe.whitelist()
    def complete_stage(self):
        self._require_exception()
        if self.status != "In Progress":
            frappe.throw("Only an in-progress piece can complete a stage")
        try:
            index = STAGES.index(self.current_stage)
        except ValueError:
            frappe.throw("Invalid production stage")
        stage = self.current_stage
        workstation = self.workstation
        responsible = self.responsible or frappe.session.user
        now = now_datetime()
        elapsed = time_diff_in_seconds(now, self.stage_started_at) / 60 if self.stage_started_at else 0
        actual_minutes = flt(max(elapsed - flt(self.blocked_minutes), 0), 2)

        if index + 1 < len(STAGES):
            self.current_stage = STAGES[index + 1]
            self.status = "Ready"
            self.stage_started_at = None
            self.workstation = None
            self.blocked_at = None
            self.blocked_minutes = 0
            self.block_reason = None
        else:
            self.current_stage = "Completed"
            self.status = "Completed"
            self.completed_at = now
            self.stage_started_at = None
            self.workstation = None
            self.blocked_at = None
            self.blocked_minutes = 0
            self.block_reason = None
        self.save()

        from wood_factory.costing import post_exception_piece_stage_cost
        costing = post_exception_piece_stage_cost(self.name, stage, actual_minutes, workstation, responsible)
        self.db_set({
            "last_stage_actual_minutes": actual_minutes,
            "last_stage_labor_cost": costing.get("labor_cost", 0),
            "last_stage_machine_cost": costing.get("machine_cost", 0),
            "last_stage_costing_status": costing.get("status", "Partial"),
        })
        self.reload()
        return {**self._summary(), "costing": costing}

    def _consume_reserved_remnant(self):
        exception = frappe.db.get_value(
            "Piece Exception",
            {"replacement_piece": self.name, "status": ["not in", ["Resolved", "Cancelled"]]},
            ["name", "suggested_remnant"],
            as_dict=True,
        )
        if not exception or not exception.suggested_remnant:
            return
        remnant = frappe.get_doc("Board Remnant", exception.suggested_remnant)
        if remnant.status == "Consumed":
            if remnant.reserved_for_piece != self.name:
                frappe.throw(f"Remnant {remnant.name} was consumed for another piece")
            return
        if remnant.status != "Reserved" or remnant.reserved_for_piece != self.name:
            frappe.throw(f"Remnant {remnant.name} must be reserved for this replacement piece before cutting")
        remnant.consume()

    def _resolve_workstation(self, preferred=None):
        workstation = preferred or self.workstation
        if workstation:
            values = frappe.db.get_value("Factory Workstation", workstation, ["stage", "status"], as_dict=True)
            if not values or values.stage != self.current_stage:
                frappe.throw(f"Workstation {workstation} does not belong to {self.current_stage}")
            if values.status != "Active":
                frappe.throw(f"Workstation {workstation} is not active")
            return workstation
        candidates = frappe.get_all(
            "Factory Workstation",
            filters={"stage": self.current_stage, "status": "Active"},
            fields=["name", "effective_minutes_per_day"],
        )
        if not candidates:
            frappe.throw(f"No active workstation is available for {self.current_stage}")
        loads = {}
        for row in candidates:
            order_load = frappe.db.count("Factory Order Stage", {"workstation": row.name, "status": ["in", ["Ready", "In Progress", "Blocked"]]})
            piece_load = frappe.db.count("Factory Piece", {"workstation": row.name, "is_exception": 1, "status": ["in", ["Ready", "In Progress", "Blocked"]]})
            loads[row.name] = order_load + piece_load
        candidates.sort(key=lambda row: ((loads[row.name] + 1) / max(flt(row.effective_minutes_per_day), 1), loads[row.name], row.name))
        return candidates[0].name

    def _summary(self):
        return {
            "piece_uid": self.piece_uid,
            "is_exception": self.is_exception,
            "current_stage": self.current_stage,
            "status": self.status,
            "responsible": self.responsible,
            "workstation": self.workstation,
            "last_stage_actual_minutes": self.last_stage_actual_minutes,
            "last_stage_labor_cost": self.last_stage_labor_cost,
            "last_stage_machine_cost": self.last_stage_machine_cost,
            "last_stage_costing_status": self.last_stage_costing_status,
        }
