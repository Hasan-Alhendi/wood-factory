from collections import Counter, defaultdict

import frappe
from frappe.utils import add_days, flt, getdate, nowdate


@frappe.whitelist()
def get_issue_analysis(from_date=None, to_date=None):
    to_date = getdate(to_date or nowdate())
    from_date = getdate(from_date or add_days(to_date, -30))
    if from_date > to_date:
        frappe.throw("From Date cannot be after To Date")

    blocked = frappe.db.sql("""
        select parent as factory_order, stage, block_reason as reason,
               blocked_minutes, responsible
        from `tabFactory Order Stage`
        where blocked_minutes > 0
          and started_at between %(from_date)s and date_add(%(to_date)s, interval 1 day)
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)
    exceptions = frappe.db.sql("""
        select factory_order, exception_type, reason, reported_stage,
               responsible, status
        from `tabPiece Exception`
        where reported_at between %(from_date)s and date_add(%(to_date)s, interval 1 day)
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    stop_reasons = Counter(_normalize_reason(row.reason) for row in blocked)
    exception_types = Counter(row.exception_type or "Other" for row in exceptions)
    stage_issues = defaultdict(lambda: {"stage": "", "stoppages": 0, "blocked_minutes": 0, "exceptions": 0})
    for row in blocked:
        item = stage_issues[row.stage]; item["stage"] = row.stage; item["stoppages"] += 1; item["blocked_minutes"] += flt(row.blocked_minutes)
    for row in exceptions:
        stage = row.reported_stage or "Unknown"
        item = stage_issues[stage]; item["stage"] = stage; item["exceptions"] += 1

    stages = sorted(stage_issues.values(), key=lambda row: (-(row["blocked_minutes"] + row["exceptions"] * 60), row["stage"]))
    total_blocked = sum(flt(row.blocked_minutes) for row in blocked)
    return {
        "summary": {"stoppages": len(blocked), "blocked_hours": flt(total_blocked / 60, 2), "exceptions": len(exceptions), "affected_orders": len({row.factory_order for row in blocked + exceptions})},
        "stop_reasons": _counter_rows(stop_reasons),
        "exception_types": _counter_rows(exception_types),
        "stages": stages,
    }


def _normalize_reason(reason):
    text = (reason or "Unspecified").strip().lower()
    keywords = {
        "Machine Breakdown": ("machine", "saw", "breakdown", "عطل", "ماكينة", "منشار"),
        "Material Shortage": ("material", "stock", "shortage", "نقص", "مادة", "لوح"),
        "Cutting Error": ("cut", "dimension", "قص", "قياس"),
        "Worker Error": ("worker", "operator", "عامل", "خطأ بشري"),
        "Waiting / Dependency": ("wait", "waiting", "previous", "انتظار", "بانتظار"),
    }
    for category, terms in keywords.items():
        if any(term in text for term in terms):
            return category
    return "Other"


def _counter_rows(counter):
    total = sum(counter.values())
    return [{"reason": name, "count": count, "percent": flt(count / total * 100, 2) if total else 0} for name, count in counter.most_common()]
