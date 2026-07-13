import frappe

from wood_factory.reports import get_factory_report_data


@frappe.whitelist()
def get_reports(from_date=None, to_date=None, company=None, customer=None, status=None):
    return get_factory_report_data(
        from_date=from_date,
        to_date=to_date,
        company=company,
        customer=customer,
        status=status,
    )
