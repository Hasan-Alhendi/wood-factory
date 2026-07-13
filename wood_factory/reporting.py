import frappe
from frappe.utils import add_days, date_diff, flt, getdate, nowdate


DEFAULT_DAYS = 30


def get_factory_report_data(from_date=None, to_date=None, company=None, customer=None, status=None):
    to_date = getdate(to_date or nowdate())
    from_date = getdate(from_date or add_days(to_date, -DEFAULT_DAYS))
    if from_date > to_date:
        frappe.throw("From Date cannot be after To Date")
    company = company or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Company is required so financial values are not mixed across currencies")
    currency = frappe.db.get_value("Company", company, "default_currency") or "USD"

    filters = {"company": company, "order_date": ["between", [from_date, to_date]]}
    filters["status"] = status if status else ["!=", "Cancelled"]
    if customer:
        filters["customer"] = customer
    orders = frappe.get_all(
        "Factory Order",
        filters=filters,
        fields=[
            "name", "sales_order", "customer", "company", "currency", "order_date",
            "expected_delivery_date", "status", "costing_status", "customer_material_cost",
            "internal_rework_material_cost", "remnant_recovery_value", "customer_labor_cost",
            "internal_rework_labor_cost", "customer_machine_cost", "internal_rework_machine_cost",
            "total_labor_cost", "total_machine_cost", "waste_cost_within_material",
            "customer_attributable_cost", "factory_error_cost", "total_actual_cost",
        ],
        order_by="order_date desc, name desc",
        limit_page_length=0,
    )
    _attach_profit(orders, currency)
    order_names = [row.name for row in orders]
    return {
        "period": {"from_date": from_date, "to_date": to_date, "days": date_diff(to_date, from_date) + 1},
        "filters": {"company": company, "customer": customer, "status": status},
        "currency": currency,
        "financial": _financial_summary(orders, currency),
        "orders": orders,
        "customers": _group_orders(orders, "customer"),
        "months": _group_orders(orders, "month"),
        "waste": _waste_metrics(order_names),
        "operations": _operational_metrics(from_date, to_date, company, customer),
    }


def _attach_profit(orders, currency):
    sales_order_names = [row.sales_order for row in orders if row.sales_order]
    revenue_map = {}
    if sales_order_names:
        revenue_field = _revenue_field()
        rows = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", sales_order_names]},
            fields=["name", revenue_field],
            limit_page_length=0,
        )
        revenue_map = {row.name: flt(row.get(revenue_field), 2) for row in rows}
    for row in orders:
        revenue = flt(revenue_map.get(row.sales_order), 2)
        customer_cost = flt(row.customer_attributable_cost, 2)
        actual_cost = flt(row.total_actual_cost, 2)
        factory_error = flt(row.factory_error_cost, 2)
        row.update({
            "currency": row.currency or currency,
            "revenue": revenue,
            "profit_before_factory_errors": flt(revenue - customer_cost, 2),
            "net_profit": flt(revenue - actual_cost, 2),
            "gross_margin_percent": flt((revenue - actual_cost) / revenue * 100, 2) if revenue else 0,
            "factory_error_impact_percent": flt(factory_error / revenue * 100, 2) if revenue else 0,
            "costing_complete": row.costing_status == "Complete",
        })


def _revenue_field():
    meta = frappe.get_meta("Sales Order")
    for fieldname in ("base_net_total", "net_total", "base_grand_total", "grand_total"):
        if meta.has_field(fieldname):
            return fieldname
    frappe.throw("Sales Order does not contain a supported revenue total field")


def _financial_summary(orders, currency):
    def total(fieldname):
        return flt(sum(flt(row.get(fieldname)) for row in orders), 2)
    revenue = total("revenue")
    actual_cost = total("total_actual_cost")
    customer_cost = total("customer_attributable_cost")
    error_cost = total("factory_error_cost")
    return {
        "currency": currency,
        "order_count": len(orders),
        "complete_costing_orders": sum(1 for row in orders if row.costing_complete),
        "incomplete_costing_orders": sum(1 for row in orders if not row.costing_complete),
        "profitable_orders": sum(1 for row in orders if flt(row.net_profit) >= 0),
        "loss_orders": sum(1 for row in orders if flt(row.net_profit) < 0),
        "revenue": revenue,
        "customer_material_cost": total("customer_material_cost"),
        "customer_labor_cost": total("customer_labor_cost"),
        "customer_machine_cost": total("customer_machine_cost"),
        "factory_error_cost": error_cost,
        "waste_cost": total("waste_cost_within_material"),
        "remnant_recovery": total("remnant_recovery_value"),
        "customer_attributable_cost": customer_cost,
        "total_actual_cost": actual_cost,
        "profit_before_factory_errors": flt(revenue - customer_cost, 2),
        "net_profit": flt(revenue - actual_cost, 2),
        "gross_margin_percent": flt((revenue - actual_cost) / revenue * 100, 2) if revenue else 0,
        "factory_error_impact_percent": flt(error_cost / revenue * 100, 2) if revenue else 0,
    }


def _group_orders(orders, mode):
    grouped = {}
    for row in orders:
        key = getdate(row.order_date).strftime("%Y-%m") if mode == "month" else (row.customer or "Unassigned")
        label = "month" if mode == "month" else "customer"
        metric = grouped.setdefault(key, {label: key, "orders": 0, "revenue": 0, "actual_cost": 0, "net_profit": 0, "factory_error_cost": 0})
        metric["orders"] += 1
        metric["revenue"] += flt(row.revenue)
        metric["actual_cost"] += flt(row.total_actual_cost)
        metric["net_profit"] += flt(row.net_profit)
        metric["factory_error_cost"] += flt(row.factory_error_cost)
    rows = list(grouped.values())
    for row in rows:
        for key in ("revenue", "actual_cost", "net_profit", "factory_error_cost"):
            row[key] = flt(row[key], 2)
        row["margin_percent"] = flt(row["net_profit"] / row["revenue"] * 100, 2) if row["revenue"] else 0
    return sorted(rows, key=(lambda row: row["month"]) if mode == "month" else (lambda row: (-row["revenue"], row["customer"])))


def _operational_metrics(from_date, to_date, company, customer=None):
    params = {"from_date": from_date, "to_date": add_days(to_date, 1), "company": company, "customer": customer}
    customer_condition = "and o.customer=%(customer)s" if customer else ""
    normal = frappe.db.sql(
        f"""select s.stage, s.workstation, s.responsible, s.actual_minutes, s.blocked_minutes,
                   s.labor_cost, s.machine_cost, 0 as internal_rework
              from `tabFactory Order Stage` s
              inner join `tabFactory Order` o on o.name=s.parent
             where s.status='Completed' and o.company=%(company)s
               and s.completed_at >= %(from_date)s and s.completed_at < %(to_date)s
               {customer_condition}""",
        params,
        as_dict=True,
    )
    exception = []
    if frappe.db.exists("DocType", "Factory Piece Stage Cost"):
        exception = frappe.db.sql(
            f"""select c.production_stage as stage, c.workstation, c.responsible, c.actual_minutes,
                       0 as blocked_minutes, c.labor_cost, c.machine_cost, 1 as internal_rework
                  from `tabFactory Piece Stage Cost` c
                  inner join `tabFactory Order` o on o.name=c.factory_order
                 where o.company=%(company)s and c.costed_on >= %(from_date)s and c.costed_on < %(to_date)s
                   {customer_condition}""",
            params,
            as_dict=True,
        )
    rows = normal + exception
    stage_map, worker_map, workstation_map = {}, {}, {}
    for row in rows:
        values = (
            flt(row.actual_minutes), flt(row.blocked_minutes), flt(row.labor_cost),
            flt(row.machine_cost), flt(row.actual_minutes) if row.internal_rework else 0,
        )
        _accumulate(stage_map, row.stage or "Unassigned", "stage", values)
        _accumulate(worker_map, row.responsible or "Unassigned", "worker", values)
        _accumulate(workstation_map, row.workstation or "Unassigned", "workstation", values)
    stages = _finish_metrics(stage_map, "stage")
    workers = _finish_metrics(worker_map, "worker")
    workstations = _finish_metrics(workstation_map, "workstation")
    stages.sort(key=lambda row: (-row["work_minutes"], row["stage"]))
    workers.sort(key=lambda row: (-row["completed"], -row["work_minutes"], row["worker"]))
    workstations.sort(key=lambda row: (-row["work_minutes"], row["workstation"]))
    return {
        "summary": {
            "completed_operations": len(rows),
            "work_hours": flt(sum(flt(row.actual_minutes) for row in rows) / 60, 2),
            "blocked_hours": flt(sum(flt(row.blocked_minutes) for row in rows) / 60, 2),
            "rework_hours": flt(sum(flt(row.actual_minutes) for row in rows if row.internal_rework) / 60, 2),
        },
        "stages": stages,
        "workers": workers[:100],
        "workstations": workstations[:100],
    }


def _accumulate(container, name, label, values):
    minutes, blocked, labor, machine, rework = values
    row = container.setdefault(name, {label: name, "completed": 0, "work_minutes": 0, "blocked_minutes": 0, "labor_cost": 0, "machine_cost": 0, "rework_minutes": 0})
    row["completed"] += 1
    row["work_minutes"] += minutes
    row["blocked_minutes"] += blocked
    row["labor_cost"] += labor
    row["machine_cost"] += machine
    row["rework_minutes"] += rework


def _finish_metrics(container, label):
    rows = []
    for row in container.values():
        for key in ("work_minutes", "blocked_minutes", "labor_cost", "machine_cost", "rework_minutes"):
            row[key] = flt(row[key], 2)
        row["avg_minutes"] = flt(row["work_minutes"] / row["completed"], 2) if row["completed"] else 0
        elapsed = row["work_minutes"] + row["blocked_minutes"]
        row["blocked_percent"] = flt(row["blocked_minutes"] / elapsed * 100, 2) if elapsed else 0
        rows.append(row)
    return rows


def _waste_metrics(order_names):
    empty = {"summary": {"cutting_orders": 0, "gross_unused_cost": 0, "recovered_value": 0, "explicit_scrap_cost": 0, "net_waste_cost": 0, "recovery_percent": 0}, "materials": [], "orders": []}
    if not order_names:
        return empty
    cutting_orders = frappe.get_all(
        "Cutting Order",
        filters={"factory_order": ["in", order_names]},
        fields=["name", "factory_order", "board_item", "board_count", "waste_percent", "order_type"],
        limit_page_length=0,
    )
    ledger_rows = frappe.get_all(
        "Factory Cost Ledger",
        filters={"factory_order": ["in", order_names], "status": "Posted"},
        fields=["cutting_order", "transaction_type", "amount"],
        limit_page_length=0,
    )
    ledger_map = {}
    for row in ledger_rows:
        if not row.cutting_order:
            continue
        values = ledger_map.setdefault(row.cutting_order, {"material": 0, "recovery": 0, "scrap": 0})
        if row.transaction_type in ("Customer Material Consumption", "Internal Replacement Material"):
            values["material"] += flt(row.amount)
        elif row.transaction_type == "Remnant Recovery":
            values["recovery"] += abs(min(flt(row.amount), 0))
        elif row.transaction_type == "Waste Cost":
            values["scrap"] += flt(row.amount)
    material_map, order_rows = {}, []
    for cutting in cutting_orders:
        costs = ledger_map.get(cutting.name, {"material": 0, "recovery": 0, "scrap": 0})
        gross_unused = flt(costs["material"] * flt(cutting.waste_percent) / 100, 2)
        item = {
            "cutting_order": cutting.name, "factory_order": cutting.factory_order,
            "board_item": cutting.board_item, "order_type": cutting.order_type,
            "board_count": flt(cutting.board_count), "waste_percent": flt(cutting.waste_percent, 2),
            "gross_unused_cost": gross_unused, "recovered_value": flt(costs["recovery"], 2),
            "explicit_scrap_cost": flt(costs["scrap"], 2),
            "net_waste_cost": flt(max(gross_unused - costs["recovery"], 0) + costs["scrap"], 2),
        }
        order_rows.append(item)
        material = material_map.setdefault(cutting.board_item or "Unassigned", {"board_item": cutting.board_item or "Unassigned", "cutting_orders": 0, "boards": 0, "gross_unused_cost": 0, "recovered_value": 0, "explicit_scrap_cost": 0, "net_waste_cost": 0})
        material["cutting_orders"] += 1
        material["boards"] += item["board_count"]
        for key in ("gross_unused_cost", "recovered_value", "explicit_scrap_cost", "net_waste_cost"):
            material[key] += item[key]
    materials = list(material_map.values())
    for row in materials:
        for key in ("boards", "gross_unused_cost", "recovered_value", "explicit_scrap_cost", "net_waste_cost"):
            row[key] = flt(row[key], 2)
    materials.sort(key=lambda row: (-row["net_waste_cost"], row["board_item"]))
    order_rows.sort(key=lambda row: (-row["net_waste_cost"], row["cutting_order"]))
    summary = {
        "cutting_orders": len(cutting_orders),
        "gross_unused_cost": flt(sum(row["gross_unused_cost"] for row in order_rows), 2),
        "recovered_value": flt(sum(row["recovered_value"] for row in order_rows), 2),
        "explicit_scrap_cost": flt(sum(row["explicit_scrap_cost"] for row in order_rows), 2),
        "net_waste_cost": flt(sum(row["net_waste_cost"] for row in order_rows), 2),
    }
    summary["recovery_percent"] = flt(summary["recovered_value"] / summary["gross_unused_cost"] * 100, 2) if summary["gross_unused_cost"] else 0
    return {"summary": summary, "materials": materials, "orders": order_rows}
