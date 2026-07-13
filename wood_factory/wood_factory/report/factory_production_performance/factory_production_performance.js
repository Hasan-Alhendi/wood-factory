frappe.query_reports["Factory Production Performance"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company")},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), -30)},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today()},
        {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
        {fieldname: "group_by", label: __("Group By"), fieldtype: "Select", options: "Stage\nWorker\nWorkstation", default: "Stage", reqd: 1},
    ],
};
