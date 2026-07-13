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
    if customer:
        filters["customer"] = customer
    if status:
        filters["status"] = status

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
    )
    _attach_revenue_and_profit(orders, currency)
    order_names = [row.name for row in orders]

    financial = _financial_summary(orders, currency)
    operations = _operational_metrics(from_date, to_date, company, customer)
    waste = _waste_metrics(order_names)
    customers = _customer_metrics(orders)
    months = _monthly_metrics(orders)

    return {
        "period": {"from_date": from_date, "to_date": to_date, "days": date_diff(to_date, from_date) + 1},
        "filters": {"company": company, "customer": customer, "status": status},
        "currency": currency,
        "financial": financial,
        "orders": orders,
        "customers": customers,
        "months": months,
        "waste": waste,
        "operations": operations,
    }


def _attach_revenue_and_profit(orders, currency):
    sales_order_names = [row.sales_order for row in orders if row.sales_order]
    revenue_map = {}
    if sales_order_names:
        revenue_field = _sales_revenue_field()
        rows = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", sales_order_names]},
            fields=["name", revenue_field],
        )
        revenue_map = {row.name: flt(row.get(revenue_field), 2) for row in rows}

    for row in orders:
        revenue = flt(revenue_map.get(row.sales_order), 2)
        customer_cost = flt(row.customer_attributable_cost, 2)
        actual_cost = flt(row.total_actual_cost, 2)
        factory_error = flt(row.factory_error_cost, 2)
        profit_before_errors = flt(revenue - customer_cost, 2)
        net_profit = flt(revenue - actual_cost, 2)
        row.update({
            "currency": row.currency or currency,
            "revenue": revenue,
            "profit_before_factory_errors": profit_before_errors,
            "net_profit": net_profit,
            "gross_margin_percent": flt(net_profit / revenue * 100, 2) if revenue else 0,
            "factory_error_impact_percent": flt(factory_error / revenue * 100, 2) if revenue else 0,
            "costing_complete": row.costing_status == "Complete",
        })


def _sales_revenue_field():
    meta = frappe.get_meta("Sales Order")
    for fieldname in ("base_net_total", "net_total", "base_grand_total", "grand_total"):
        if meta.has_field(fieldname):
            return fieldname
    frappe.throw("Sales Order does not contain a supported revenue total field")


def _financial_summary(orders, currency):
    summary = {
        "currency": currency,
        "order_count": len(orders),
        "complete_costing_orders": sum(1 for row in orders if row.costing_complete),
        "incomplete_costing_orders": sum(1 for row in orders if not row.costing_complete),
        "revenue": flt(sum(flt(row.revenue) for row in orders), 2),
        "customer_material_cost": flt(sum(flt(row.customer_material_cost) for row in orders), 2),
        "customer_labor_cost": flt(sum(flt(row.customer_labor_cost) for row in orders), 2),
        "customer_machine_cost": flt(sum(flt(row.customer_machine_cost) for row in orders), 2),
        "factory_error_cost": flt(sum(flt(row.factory_error_cost) for row in orders), 2),
        "waste_cost": flt(sum(flt(row.waste_cost_within_material) for row in orders), 2),
        "remnant_recovery": flt(sum(flt(row.remnant_recovery_value) for row in orders), 2),
        "customer_attributable_cost": flt(sum(flt(row.customer_attributable_cost) for row in orders), 2),
        "total_actual_cost": flt(sum(flt(row.total_actual_cost) for row in orders), 2),
    }
    summary["profit_before_factory_errors"] = flt(summary["revenue"] - summary["customer_attributable_cost"], 2)
    summary["net_profit"] = flt(summary["revenue"] - summary["total_actual_cost"], 2)
    summary["gross_margin_percent"] = flt(summary["net_profit"] / summary["revenue"] * 100, 2) if summary["revenue"] else 0
    summary["factory_error_impact_percent"] = flt(summary["factory_error_cost"] / summary["revenue"] * 100, 2) if summary["revenue"] else 0
    summary["profitable_orders"] = sum(1 for row in orders if flt(row.net_profit) >= 0)
    summary["loss_orders"] = sum(1 for row in orders if flt(row.net_profit) < 0)
    return summary


def _operational_metrics(from_date, to_date, company, customer=None):
    params = {"from_date": from_date, "to_date": add_days(to_date, 1), "company": company, "customer": customer}
    customer_condition = "and o.customer=%(customer)s" if customer else ""
    normal = frappe.db.sql(
        f"""
        select s.stage, s.workstation, s.responsible, s.actual_minutes, s.blocked_minutes,
               s.labor_cost, s.machine_cost, 0 as internal_rework
        from `tabFactory Order Stage` s
        inner join `tabFactory Order` o on o.name=s.parent
        where s.status='Completed' and o.company=%(company)s
          and s.completed_at >= %(from_date)s and s.completed_at < %(to_date)s
          {customer_condition}
        """,
        params,
        as_dict=True,
    )
    exception = []
    if frappe.db.exists("DocType", "Factory Piece Stage Cost"):
        exception = frappe.db.sql(
            f"""
            select c.production_stage as stage, c.workstation, c.responsible, c.actual_minutes,
                   0 as blocked_minutes, c.labor_cost, c.machine_cost, 1 as internal_rework
            from `tabFactory Piece Stage Cost` c
            inner join `tabFactory Order` o on o.name=c.factory_order
            where o.company=%(company)s and c.costed_on >= %(from_date)s and c.costed_on < %(to_date)s
              {customer_condition}
            """,
            params,
            as_dict=True,
        )
    rows = normal + exception
    stage_map, worker_map, workstation_map = {}, {}, {}
    for row in rows:
        minutes = flt(row.actual_minutes)
        blocked = flt(row.blocked_minutes)
        labor_cost = flt(row.labor_cost)
        machine_cost = flt(row.machine_cost)
        rework_minutes = minutes if row.internal_rework else 0

        stage = stage_map.setdefault(row.stage or "Unassigned", {
            "stage": row.stage or "Unassigned", "completed": 0, "work_minutes": 0,
            "blocked_minutes": 0, "labor_cost": 0, "machine_cost": 0, "rework_minutes": 0,
        })
        _accumulate_operation(stage, minutes, blocked, labor_cost, machine_cost, rework_minutes)

        worker_name = row.responsible or "Unassigned"
        worker = worker_map.setdefault(worker_name, {
            "worker": worker_name, "completed": 0, "work_minutes": 0,
            "blocked_minutes": 0, "labor_cost": 0, "machine_cost": 0, "rework_minutes": 0,
        })
        _accumulate_operation(worker, minutes, blocked, labor_cost, machine_cost, rework_minutes)

        workstation_name = row.workstation or "Unassigned"
        workstation = workstation_map.setdefault(workstation_name, {
            "workstation": workstation_name, "completed": 0, "work_minutes": 0,
            "blocked_minutes": 0, "labor_cost": 0, "machine_cost": 0, "rework_minutes": 0,
        })
        _accumulate_operation(workstation, minutes, blocked, labor_cost, machine_cost, rework_minutes)

    stages = [_finish_operation(row) for row in stage_map.values()]
    workers = [_finish_operation(row) for row in worker_map.values()]
    workstations = [_finish_operation(row) for row in workstation_map.values()]
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
        "workers": workers[:30],
        "workstations": workstations[:30],
    }


def _accumulate_operation(target, minutes, blocked, labor_cost, machine_cost, rework_minutes):
    target["completed"] += 1
    target["work_minutes"] += minutes
    target["blocked_minutes"] += blocked
    target["labor_cost"] += labor_cost
    target["machine_cost"] += machine_cost
    target["rework_minutes"] += rework_minutes


def _finish_operation(row):
    row["work_minutes"] = flt(row["work_minutes"], 2)
    row["blocked_minutes"] = flt(row["blocked_minutes"], 2)
    row["labor_cost"] = flt(row["labor_cost"], 2)
    row["machine_cost"] = flt(row["machine_cost"], 2)
    row["rework_minutes"] = flt(row["rework_minutes"], 2)
    row["avg_minutes"] = flt(row["work_minutes"] / row["completed"], 2) if row["completed"] else 0
    elapsed = row["work_minutes"] + row["blocked_minutes"]
    row["blocked_percent"] = flt(row["blocked_minutes"] / elapsed * 100, 2) if elapsed else 0
    return row


def _waste_metrics(order_names):
    if not order_names:
        return {"summary": {"cutting_orders": 0, "gross_unused_cost": 0, "recovered_value": 0, "explicit_scrap_cost": 0, "net_waste_cost": 0}, "materials": [], "orders": []}
    cutting_orders = frappe.get_all(
        "Cutting Order",
        filters={"factory_order": ["in", order_names]},
        fields=["name", "factory_order", "board_item", "board_count", "waste_percent", "order_type"],
    )
    ledger_rows = frappe.get_all(
        "Factory Cost Ledger",
        filters={"factory_order": ["in", order_names], "status": "Posted"},
        fields=["cutting_order", "transaction_type", "amount"],
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
        net_waste = flt(max(gross_unused - costs["recovery"], 0) + costs["scrap"], 2)
        row = {
            "cutting_order": cutting.name, "factory_order": cutting.factory_order,
            "board_item": cutting.board_item, "order_type": cutting.order_type,
            "board_count": cutting.board_count, "waste_percent": flt(cutting.waste_percent, 2),
            "gross_unused_cost": gross_unused, "recovered_value": flt(costs["recovery"], 2),
            "explicit_scrap_cost": flt(costs["scrap"], 2), "net_waste_cost": net_waste,
        }
        order_rows.append(row)
        material = material_map.setdefault(cutting.board_item or "Unassigned", {
            "board_item": cutting.board_item or "Unassigned", "cutting_orders": 0, "boards": 0,
            "gross_unused_cost": 0, "recovered_value": 0, "explicit_scrap_cost": 0, "net_waste_cost": 0,
        })
        material["cutting_orders"] += 1
        material["boards"] += flt(cutting.board_count)
        for key in ("gross_unused_cost", "recovered_value", "explicit_scrap_cost", "net_waste_cost"):
            material[key] += row[key]

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
    return {"summary": summary, "materials": materials, "orders": order_rows[:50]}


def _customer_metrics(orders):
    grouped = {}
    for row in orders:
        customer = row.customer or "Unassigned"
        metric = grouped.setdefault(customer, {"customer": customer, "orders": 0, "revenue": 0, "actual_cost": 0, "net_profit": 0, "factory_error_cost": 0})
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
    rows.sort(key=lambda row: (-row["revenue"], row["customer"]))
    return rows


def _monthly_metrics(orders):
    grouped = {}
    for row in orders:
        month = getdate(row.order_date).strftime("%Y-%m")
        metric = grouped.setdefault(month, {"month": month, "orders": 0, "revenue": 0, "actual_cost": 0, "net_profit": 0, "factory_error_cost": 0})
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
    return sorted(rows, key=lambda row: row["month"])
