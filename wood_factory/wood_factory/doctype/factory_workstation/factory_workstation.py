import frappe
from frappe.model.document import Document
from frappe.utils import flt


PRIORITY_WEIGHT = {"Urgent": 4000, "High": 3000, "Normal": 2000, "Low": 1000}


class FactoryWorkstation(Document):
    def validate(self):
        if self.minutes_per_day <= 0:
            frappe.throw("Capacity Minutes / Day must be greater than zero")
        if not 0 < flt(self.efficiency_percent) <= 100:
            frappe.throw("Efficiency Percent must be greater than 0 and not exceed 100")
        if self.status != "Active" and not self.unavailable_reason:
            frappe.throw("Unavailable Reason is required when workstation is not active")
        if flt(self.default_labor_hourly_cost) < 0 or flt(self.machine_hourly_cost) < 0:
            frappe.throw("Hourly costing rates cannot be negative")
        if not self.company:
            try:
                from wood_factory.accounting import get_accounting_settings
                self.company = get_accounting_settings().company
            except Exception:
                self.company = None
        if self.company and not self.currency:
            self.currency = frappe.db.get_value("Company", self.company, "default_currency")
        self.effective_minutes_per_day = flt(self.minutes_per_day * flt(self.efficiency_percent) / 100, 2) if self.status == "Active" else 0

    @frappe.whitelist()
    def preview_queue_rebalancing(self):
        return self._queue_rebalancing(apply=False)

    @frappe.whitelist()
    def rebalance_waiting_queue(self):
        if self.status == "Active":
            frappe.throw("Automatic evacuation is only allowed for unavailable workstations")
        return self._queue_rebalancing(apply=True)

    def _queue_rebalancing(self, apply=False):
        waiting = frappe.db.sql("""
            select s.name as stage_row, s.parent as `order`, s.stage, s.workstation, s.status,
                   o.priority, o.expected_delivery_date, o.delay_days, o.modified
            from `tabFactory Order Stage` s
            inner join `tabFactory Order` o on o.name=s.parent
            where s.workstation=%s and s.status in ('Ready','Blocked')
            order by case o.priority when 'Urgent' then 1 when 'High' then 2 when 'Normal' then 3 else 4 end,
                     o.delay_days desc, o.expected_delivery_date asc, o.modified asc
        """, self.name, as_dict=True)
        candidates = frappe.get_all("Factory Workstation", filters={"stage": self.stage, "status": "Active", "name": ["!=", self.name]}, fields=["name", "effective_minutes_per_day"])
        loads = dict(frappe.db.sql("""
            select s.workstation, count(*) from `tabFactory Order Stage` s
            where s.stage=%s and s.workstation is not null and s.status in ('Ready','In Progress','Blocked') group by s.workstation
        """, self.stage))
        moves = []
        for job in waiting:
            target = self._best_target(candidates, loads)
            moves.append({"order": job.order, "stage_row": job.stage_row, "priority": job.priority or "Normal", "from_workstation": self.name, "to_workstation": target})
            if target:
                loads[target] = loads.get(target, 0) + 1
                if apply:
                    frappe.db.set_value("Factory Order Stage", job.stage_row, "workstation", target, update_modified=False)
                    self._record_move(job, target)
        if apply:
            frappe.db.commit()
        return {"workstation": self.name, "stage": self.stage, "waiting_jobs": len(waiting), "movable": sum(1 for row in moves if row["to_workstation"]), "moved": sum(1 for row in moves if apply and row["to_workstation"]), "moves": moves}

    def _best_target(self, candidates, loads):
        if not candidates:
            return None
        return min(candidates, key=lambda row: ((loads.get(row.name, 0) + 1) / max(flt(row.effective_minutes_per_day), 1), loads.get(row.name, 0), row.name)).name

    def _record_move(self, job, target):
        event = frappe.new_doc("Factory Order Event")
        event.update({"factory_order": job.order, "event_type": "Queue Rebalanced", "stage": job.stage, "performed_by": frappe.session.user, "details": f"Waiting stage moved from {self.name} to {target}", "reference_doctype": "Factory Workstation", "reference_name": target})
        event.flags.factory_event_insert = True
        event.insert(ignore_permissions=True)
