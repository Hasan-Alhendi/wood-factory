import frappe

from wood_factory.reports import get_factory_report_data


ALLOWED_ROLES = {"System Manager", "Manufacturing Manager", "Accounts Manager"}


@frappe.whitelist()
def get_reports(from_date=None, to_date=None, company=None, customer=None, status=None):
    if not ALLOWED_ROLES.intersection(frappe.get_roles()):
        frappe.throw("You are not permitted to view factory financial reports", frappe.PermissionError)
    return get_factory_report_data(
        from_date=from_date,
        to_date=to_date,
        company=company,
        customer=customer,
        status=status,
    )
