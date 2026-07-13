import frappe
from frappe import _

from wood_factory.reports import get_factory_report_data


GROUPS = {
    "Stage": ("stages", "stage", _("Stage")),
    "Worker": ("workers", "worker", _("Worker")),
    "Workstation": ("workstations", "workstation", _("Workstation")),
}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_factory_report_data(
        from_date=filters.from_date,
        to_date=filters.to_date,
        company=filters.company,
        customer=filters.customer,
    )
    group_by = filters.group_by or "Stage"
    collection, key, label = GROUPS.get(group_by, GROUPS["Stage"])
    currency = data["currency"]
    rows = []
    for item in data["operations"][collection]:
        rows.append({
            "entity": item.get(key),
            "completed": item.get("completed"),
            "work_hours": (item.get("work_minutes") or 0) / 60,
            "average_minutes": item.get("avg_minutes"),
            "blocked_hours": (item.get("blocked_minutes") or 0) / 60,
            "blocked_percent": item.get("blocked_percent"),
            "rework_hours": (item.get("rework_minutes") or 0) / 60,
            "labor_cost": item.get("labor_cost"),
            "machine_cost": item.get("machine_cost"),
            "operating_cost": (item.get("labor_cost") or 0) + (item.get("machine_cost") or 0),
            "currency": currency,
        })

    summary = data["operations"]["summary"]
    report_summary = [
        {"label": _("Completed Operations"), "value": summary["completed_operations"], "indicator": "Blue", "datatype": "Int"},
        {"label": _("Work Hours"), "value": summary["work_hours"], "indicator": "Green", "datatype": "Float"},
        {"label": _("Blocked Hours"), "value": summary["blocked_hours"], "indicator": "Red" if summary["blocked_hours"] else "Green", "datatype": "Float"},
        {"label": _("Rework Hours"), "value": summary["rework_hours"], "indicator": "Orange" if summary["rework_hours"] else "Green", "datatype": "Float"},
    ]
    chart = None
    if rows:
        top = sorted(rows, key=lambda row: row["work_hours"], reverse=True)[:12]
        chart = {
            "data": {
                "labels": [row["entity"] for row in top],
                "datasets": [
                    {"name": _("Work Hours"), "values": [row["work_hours"] for row in top]},
                    {"name": _("Rework Hours"), "values": [row["rework_hours"] for row in top]},
                ],
            },
            "type": "bar",
            "height": 300,
        }
    return _columns(label), rows, None, chart, report_summary


def _columns(entity_label):
    return [
        {"fieldname": "entity", "label": entity_label, "fieldtype": "Data", "width": 190},
        {"fieldname": "completed", "label": _("Completed Operations"), "fieldtype": "Int", "width": 135},
        {"fieldname": "work_hours", "label": _("Work Hours"), "fieldtype": "Float", "precision": 2, "width": 105},
        {"fieldname": "average_minutes", "label": _("Average Minutes"), "fieldtype": "Float", "precision": 2, "width": 115},
        {"fieldname": "blocked_hours", "label": _("Blocked Hours"), "fieldtype": "Float", "precision": 2, "width": 110},
        {"fieldname": "blocked_percent", "label": _("Blocked %"), "fieldtype": "Percent", "width": 95},
        {"fieldname": "rework_hours", "label": _("Rework Hours"), "fieldtype": "Float", "precision": 2, "width": 105},
        {"fieldname": "labor_cost", "label": _("Labor Cost"), "fieldtype": "Currency", "options": "currency", "width": 110},
        {"fieldname": "machine_cost", "label": _("Machine Cost"), "fieldtype": "Currency", "options": "currency", "width": 115},
        {"fieldname": "operating_cost", "label": _("Operating Cost"), "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]
