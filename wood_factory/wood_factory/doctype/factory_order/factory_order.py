import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, flt, now_datetime, nowdate, time_diff_in_seconds


STAGES = ("Cutting", "Edge Banding", "Drilling", "Assembly", "Quality Inspection", "Packing")


class FactoryOrder(Document):
    def validate(self):
        self._validate_dates()
        self._validate_accounting_dimensions()
        self._set_delay()
        self._set_priority()
        self._validate_workstations()
        self._sync_execution_state()

    def _validate_dates(self):
        if self.expected_delivery_date and self.order_date and date_diff(self.expected_delivery_date, self.order_date) < 0:
            frappe.throw("Expected delivery date cannot be before order date")
        if self.priority_override and not self.priority_reason:
            frappe.throw("Priority override reason is required")

    def _validate_accounting_dimensions(self):
        company = self.company or (frappe.db.get_value("Sales Order", self.sales_order, "company") if self.sales_order else None)
        if not company:
            return
        for fieldname, doctype in (("cost_center", "Cost Center"), ("rework_cost_center", "Cost Center"), ("project", "Project")):
            value = self.get(fieldname)
            if not value:
                continue
            dimension_company = frappe.db.get_value(doctype, value, "company")
            if dimension_company and dimension_company != company:
                frappe.throw(f"{doctype} {value} belongs to {dimension_company}, not {company}")

    def _set_delay(self):
        if not self.expected_delivery_date or self.status in ("Delivered", "Closed", "Cancelled"):
            self.delay_days = 0
            return
        self.delay_days = max(date_diff(nowdate(), self.expected_delivery_date), 0)

    def _set_priority(self):
        if self.priority_override:
            self.priority = self.priority_override
            return
        open_exceptions = 0 if self.is_new() else frappe.db.count(
            "Piece Exception", {"factory_order": self.name, "status": ["not in", ["Resolved", "Cancelled"]]}
        )
        days_left = date_diff(self.expected_delivery_date, nowdate()) if self.expected_delivery_date else 999
        if self.delay_days > 0 or open_exceptions:
            self.priority = "Urgent"
        elif days_left <= 1:
            self.priority = "High"
        elif days_left <= 3:
            self.priority = "Normal"
        else:
            self.priority = "Low"

    def _validate_workstations(self):
        for row in self.production_stages or []:
            if not row.workstation:
                continue
            workstation = frappe.db.get_value("Factory Workstation", row.workstation, ["stage", "status", "company"], as_dict=True)
            if not workstation:
                frappe.throw(f"Workstation {row.workstation} does not exist")
            if workstation.stage != row.stage:
                frappe.throw(f"Workstation {row.workstation} belongs to {workstation.stage}, not {row.stage}")
            if self.company and workstation.company and workstation.company != self.company:
                frappe.throw(f"Workstation {row.workstation} belongs to {workstation.company}, not {self.company}")
            if row.status in ("Ready", "In Progress") and workstation.status != "Active":
                frappe.throw(f"Workstation {row.workstation} is not active")

    def _sync_execution_state(self):
        stages = list(self.production_stages or [])
        if not stages:
            self.progress_percent = 0
            self.current_stage = None
            self.current_responsible = None
            return
        completed = sum(1 for row in stages if row.status in ("Completed", "Skipped"))
        self.progress_percent = flt(completed / len(stages) * 100, 2)
        current = next((row for row in stages if row.status in ("In Progress", "Blocked")), None) or next(
            (row for row in stages if row.status == "Ready"), None
        )
        self.current_stage = current.stage if current else None
        self.current_responsible = current.responsible if current else None
        if all(row.status in ("Completed", "Skipped") for row in stages):
            self.status = "Quality Inspection"
        elif any(row.status in ("In Progress", "Blocked") for row in stages):
            self.status = "In Production"

    @frappe.whitelist()
    def initialize_production_stages(self):
        if self.production_stages:
            frappe.throw("Production stages already exist")
        for index, stage in enumerate(STAGES):
            self.append("production_stages", {"stage": stage, "status": "Ready" if index == 0 else "Pending", "costing_status": "Pending"})
        self._assign_ready_workstations()
        self.save()
        self._sync_normal_pieces()
        self._record_event("Stages Initialized", details="Production stages initialized")
        return self._execution_summary()

    @frappe.whitelist()
    def auto_assign_stage(self, row_name):
        row = self._stage(row_name)
        if row.status not in ("Pending", "Ready", "Blocked"):
            frappe.throw("Only pending, ready, or blocked stages can be assigned")
        previous = row.workstation
        row.workstation = self._best_workstation(row.stage, exclude_order=self.name)
        if not row.workstation:
            frappe.throw(f"No active workstation is available for {row.stage}")
        self.save()
        self._record_event("Workstation Assigned", row.stage, details=f"{previous or 'Unassigned'} → {row.workstation}", reference_doctype="Factory Workstation", reference_name=row.workstation)
        return {"workstation": row.workstation, **self._execution_summary()}

    def _assign_ready_workstations(self):
        for row in self.production_stages or []:
            if row.status == "Ready" and not row.workstation:
                row.workstation = self._best_workstation(row.stage, exclude_order=self.name)

    def _best_workstation(self, stage, exclude_order=None):
        workstations = frappe.get_all(
            "Factory Workstation",
            filters={"stage": stage, "status": "Active"},
            fields=["name", "effective_minutes_per_day", "company"],
        )
        workstations = [row for row in workstations if not self.company or not row.company or row.company == self.company]
        if not workstations:
            return None
        loads = dict(frappe.db.sql(
            """
            select s.workstation, count(*) from `tabFactory Order Stage` s
            inner join `tabFactory Order` o on o.name=s.parent
            where s.stage=%s and s.workstation is not null and s.status in ('Ready','In Progress','Blocked')
              and (%s is null or o.name != %s) group by s.workstation
            """,
            (stage, exclude_order, exclude_order),
        ))
        workstations.sort(key=lambda row: ((loads.get(row.name, 0) + 1) / max(flt(row.effective_minutes_per_day), 1), loads.get(row.name, 0), row.name))
        return workstations[0].name

    @frappe.whitelist()
    def start_stage(self, row_name):
        row = self._stage(row_name)
        if row.status not in ("Ready", "Blocked"):
            frappe.throw("Only a ready or blocked stage can be started")
        active = next((stage for stage in self.production_stages if stage.name != row.name and stage.status == "In Progress"), None)
        if active:
            frappe.throw(f"Stage {active.stage} is already in progress")
        if not row.workstation:
            row.workstation = self._best_workstation(row.stage, exclude_order=self.name)
        if not row.workstation:
            frappe.throw(f"No active workstation is available for {row.stage}")
        workstation = frappe.db.get_value("Factory Workstation", row.workstation, ["status", "company"], as_dict=True)
        if not workstation or workstation.status != "Active":
            frappe.throw(f"Workstation {row.workstation} is not active. Reassign the stage before starting")
        if self.company and workstation.company and workstation.company != self.company:
            frappe.throw(f"Workstation {row.workstation} belongs to {workstation.company}, not {self.company}")
        now = now_datetime()
        resumed = row.status == "Blocked"
        if resumed and row.blocked_at:
            row.blocked_minutes = flt(row.blocked_minutes) + time_diff_in_seconds(now, row.blocked_at) / 60
            row.blocked_at = None
        if not row.started_at:
            row.started_at = now
        row.status = "In Progress"
        row.responsible = frappe.session.user
        self.save()
        self._sync_normal_pieces(row)
        self._record_event("Stage Resumed" if resumed else "Stage Started", row.stage, details=f"Stage handled by {frappe.session.user} on {row.workstation}", reference_doctype="Factory Workstation", reference_name=row.workstation)
        return self._execution_summary()

    @frappe.whitelist()
    def block_stage(self, row_name, reason):
        row = self._stage(row_name)
        if row.status != "In Progress":
            frappe.throw("Only an in-progress stage can be blocked")
        if not reason:
            frappe.throw("Block reason is required")
        row.status = "Blocked"
        row.block_reason = reason
        row.blocked_at = now_datetime()
        self.save()
        self._sync_normal_pieces(row)
        self._record_event("Stage Blocked", row.stage, reason=reason, reference_doctype="Factory Order Stage", reference_name=row.name)
        return self._execution_summary()

    @frappe.whitelist()
    def complete_stage(self, row_name):
        row = self._stage(row_name)
        if row.status != "In Progress":
            frappe.throw("Only an in-progress stage can be completed")
        now = now_datetime()
        row.completed_at = now
        elapsed = time_diff_in_seconds(now, row.started_at) / 60 if row.started_at else 0
        row.actual_minutes = flt(max(elapsed - flt(row.blocked_minutes), 0), 2)
        row.status = "Completed"
        row.blocked_at = None
        next_row = next((stage for stage in self.production_stages if stage.idx > row.idx and stage.status == "Pending"), None)
        if next_row:
            next_row.status = "Ready"
            if not next_row.workstation:
                next_row.workstation = self._best_workstation(next_row.stage, exclude_order=self.name)
        self.save()
        from wood_factory.costing import post_order_stage_cost
        costing = post_order_stage_cost(self.name, row.name)
        self.reload()
        self._sync_normal_pieces(next_row)
        self._record_event("Stage Completed", row.stage, details=f"Actual work time: {row.actual_minutes} minute(s) on {row.workstation or 'unassigned workstation'}; costing: {costing.get('status')}", reference_doctype="Factory Workstation" if row.workstation else "Factory Order Stage", reference_name=row.workstation or row.name)
        return {**self._execution_summary(), "costing": costing}

    @frappe.whitelist()
    def recalculate_actual_costing(self):
        from wood_factory.costing import post_order_stage_cost, recalculate_exception_piece_costs, sync_factory_order_actual_costs
        stage_results = []
        for row in self.production_stages or []:
            if row.status == "Completed" and (row.costing_status or "Pending") != "Posted":
                stage_results.append({"stage": row.stage, **post_order_stage_cost(self.name, row.name)})
        piece_results = recalculate_exception_piece_costs(self.name)
        totals = sync_factory_order_actual_costs(self.name)
        self.reload()
        return {"stages": stage_results, "exception_piece_stages": piece_results, "totals": totals}

    def _record_event(self, event_type, stage=None, reason=None, details=None, reference_doctype=None, reference_name=None):
        event = frappe.new_doc("Factory Order Event")
        event.update({"factory_order": self.name, "event_type": event_type, "stage": stage, "event_at": now_datetime(), "performed_by": frappe.session.user, "reason": reason, "details": details, "reference_doctype": reference_doctype, "reference_name": reference_name})
        event.flags.factory_event_insert = True
        event.insert(ignore_permissions=True)

    def _sync_normal_pieces(self, stage=None):
        if not frappe.db.exists("DocType", "Factory Piece"):
            return
        stage = stage or next((row for row in self.production_stages if row.status in ("In Progress", "Blocked", "Ready")), None)
        values = {"current_stage": stage.stage if stage else "Completed", "status": stage.status if stage else "Completed", "responsible": stage.responsible if stage else None, "stage_started_at": stage.started_at if stage else None, "workstation": stage.workstation if stage else None}
        if values["status"] == "Pending":
            values["status"] = "Ready"
        available = {field.fieldname for field in frappe.get_meta("Factory Piece").fields}
        frappe.db.set_value("Factory Piece", {"factory_order": self.name, "is_exception": 0}, {key: value for key, value in values.items() if key in available}, update_modified=False)

    def _stage(self, row_name):
        row = next((stage for stage in self.production_stages if stage.name == row_name), None)
        if not row:
            frappe.throw("Production stage not found")
        return row

    def _execution_summary(self):
        return {"status": self.status, "current_stage": self.current_stage, "current_responsible": self.current_responsible, "progress_percent": self.progress_percent, "costing_status": self.costing_status, "total_actual_cost": self.total_actual_cost}
