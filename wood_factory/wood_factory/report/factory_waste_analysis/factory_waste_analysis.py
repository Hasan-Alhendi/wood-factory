import frappe
from frappe import _

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
    rows = []
    for row in data["waste"]["orders"]:
        rows.append({**row, "currency": currency})

    summary = data["waste"]["summary"]
    report_summary = [
        {"label": _("Gross Unused Value"), "value": summary["gross_unused_cost"], "indicator": "Orange", "datatype": "Currency", "currency": currency},
        {"label": _("Recovered Remnant Value"), "value": summary["recovered_value"], "indicator": "Green", "datatype": "Currency", "currency": currency},
        {"label": _("Explicit Scrap Cost"), "value": summary["explicit_scrap_cost"], "indicator": "Red" if summary["explicit_scrap_cost"] else "Green", "datatype": "Currency", "currency": currency},
        {"label": _("Net Waste Cost"), "value": summary["net_waste_cost"], "indicator": "Red" if summary["net_waste_cost"] else "Green", "datatype": "Currency", "currency": currency},
        {"label": _("Recovery Rate"), "value": summary["recovery_percent"], "indicator": "Green", "datatype": "Percent"},
    ]
    chart = None
    materials = data["waste"]["materials"][:12]
    if materials:
        chart = {
            "data": {
                "labels": [row["board_item"] for row in materials],
                "datasets": [
                    {"name": _("Gross Unused"), "values": [row["gross_unused_cost"] for row in materials]},
                    {"name": _("Recovered"), "values": [row["recovered_value"] for row in materials]},
                    {"name": _("Net Waste"), "values": [row["net_waste_cost"] for row in materials]},
                ],
            },
            "type": "bar",
            "height": 300,
        }
    return _columns(), rows, None, chart, report_summary


def _columns():
    return [
        {"fieldname": "cutting_order", "label": _("Cutting Order"), "fieldtype": "Link", "options": "Cutting Order", "width": 150},
        {"fieldname": "factory_order", "label": _("Factory Order"), "fieldtype": "Link", "options": "Factory Order", "width": 150},
        {"fieldname": "board_item", "label": _("Board Material"), "fieldtype": "Link", "options": "Item", "width": 180},
        {"fieldname": "order_type", "label": _("Order Type"), "fieldtype": "Data", "width": 135},
        {"fieldname": "board_count", "label": _("Boards"), "fieldtype": "Float", "width": 80},
        {"fieldname": "waste_percent", "label": _("Layout Waste %"), "fieldtype": "Percent", "width": 110},
        {"fieldname": "gross_unused_cost", "label": _("Gross Unused Value"), "fieldtype": "Currency", "options": "currency", "width": 145},
        {"fieldname": "recovered_value", "label": _("Recovered Remnant Value"), "fieldtype": "Currency", "options": "currency", "width": 165},
        {"fieldname": "explicit_scrap_cost", "label": _("Explicit Scrap Cost"), "fieldtype": "Currency", "options": "currency", "width": 140},
        {"fieldname": "net_waste_cost", "label": _("Net Waste Cost"), "fieldtype": "Currency", "options": "currency", "width": 130},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]
