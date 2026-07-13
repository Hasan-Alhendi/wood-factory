import frappe
from frappe import _
from frappe.utils import flt

from wood_factory.reports import get_factory_report_data


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_factory_report_data(
        from_date=filters.from_date,
        to_date=filters.to_date,
        company=filters.company,
        customer=filters.customer,
        status=filters.status,
    )
    currency = data["currency"]
    columns = _columns()
    rows = []
    for order in data["orders"]:
        rows.append({
            "factory_order": order.name,
            "sales_order": order.sales_order,
            "customer": order.customer,
            "order_date": order.order_date,
            "status": order.status,
            "revenue": order.revenue,
            "customer_attributable_cost": order.customer_attributable_cost,
            "profit_before_factory_errors": order.profit_before_factory_errors,
            "factory_error_cost": order.factory_error_cost,
            "waste_cost": order.waste_cost_within_material,
            "total_actual_cost": order.total_actual_cost,
            "net_profit": order.net_profit,
            "gross_margin_percent": order.gross_margin_percent,
            "costing_status": order.costing_status,
            "currency": currency,
        })

    summary = data["financial"]
    report_summary = [
        {"label": _("Net Sales"), "value": summary["revenue"], "indicator": "Blue", "datatype": "Currency", "currency": currency},
        {"label": _("Actual Cost"), "value": summary["total_actual_cost"], "indicator": "Orange", "datatype": "Currency", "currency": currency},
        {"label": _("Net Profit"), "value": summary["net_profit"], "indicator": "Green" if summary["net_profit"] >= 0 else "Red", "datatype": "Currency", "currency": currency},
        {"label": _("Gross Margin"), "value": summary["gross_margin_percent"], "indicator": "Green" if summary["gross_margin_percent"] >= 0 else "Red", "datatype": "Percent"},
        {"label": _("Factory Error Cost"), "value": summary["factory_error_cost"], "indicator": "Red" if summary["factory_error_cost"] else "Green", "datatype": "Currency", "currency": currency},
        {"label": _("Incomplete Costing"), "value": summary["incomplete_costing_orders"], "indicator": "Red" if summary["incomplete_costing_orders"] else "Green", "datatype": "Int"},
    ]
    chart = _chart(data["months"])
    message = None
    if summary["incomplete_costing_orders"]:
        message = _("{0} order(s) have incomplete costing. Their profit is based on currently recorded costs only.").format(summary["incomplete_costing_orders"])
    return columns, rows, message, chart, report_summary


def _columns():
    return [
        {"fieldname": "factory_order", "label": _("Factory Order"), "fieldtype": "Link", "options": "Factory Order", "width": 150},
        {"fieldname": "sales_order", "label": _("Sales Order"), "fieldtype": "Link", "options": "Sales Order", "width": 140},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 180},
        {"fieldname": "order_date", "label": _("Order Date"), "fieldtype": "Date", "width": 105},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 125},
        {"fieldname": "revenue", "label": _("Net Sales"), "fieldtype": "Currency", "options": "currency", "width": 125},
        {"fieldname": "customer_attributable_cost", "label": _("Customer Production Cost"), "fieldtype": "Currency", "options": "currency", "width": 155},
        {"fieldname": "profit_before_factory_errors", "label": _("Profit Before Errors"), "fieldtype": "Currency", "options": "currency", "width": 145},
        {"fieldname": "factory_error_cost", "label": _("Factory Error Cost"), "fieldtype": "Currency", "options": "currency", "width": 140},
        {"fieldname": "waste_cost", "label": _("Waste Cost"), "fieldtype": "Currency", "options": "currency", "width": 115},
        {"fieldname": "total_actual_cost", "label": _("Actual Cost"), "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "net_profit", "label": _("Net Profit"), "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "gross_margin_percent", "label": _("Margin %"), "fieldtype": "Percent", "width": 95},
        {"fieldname": "costing_status", "label": _("Costing Status"), "fieldtype": "Data", "width": 115},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def _chart(months):
    if not months:
        return None
    return {
        "data": {
            "labels": [row["month"] for row in months],
            "datasets": [
                {"name": _("Net Sales"), "values": [flt(row["revenue"], 2) for row in months]},
                {"name": _("Actual Cost"), "values": [flt(row["actual_cost"], 2) for row in months]},
                {"name": _("Net Profit"), "values": [flt(row["net_profit"], 2) for row in months]},
            ],
        },
        "type": "line",
        "height": 280,
        "colors": ["#2490ef", "#f59e0b", "#16a34a"],
        "axis_options": {"xIsSeries": 1},
    }
