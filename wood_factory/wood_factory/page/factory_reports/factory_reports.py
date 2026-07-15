import frappe

from wood_factory.reports import get_factory_report_data
from wood_factory.security import ACCOUNTING_ROLES, MANAGEMENT_ROLES, require_any_role


@frappe.whitelist()
def get_reports(from_date=None, to_date=None, company=None, customer=None, status=None):
    require_any_role(ACCOUNTING_ROLES | MANAGEMENT_ROLES, "You are not permitted to view factory financial reports")
    return get_factory_report_data(
        from_date=from_date,
        to_date=to_date,
        company=company,
        customer=customer,
        status=status,
    )
