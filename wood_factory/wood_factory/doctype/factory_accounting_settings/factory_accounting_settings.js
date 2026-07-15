frappe.ui.form.on("Factory Accounting Settings", {
    setup(frm) {
        frm.set_query("customer_cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("internal_rework_cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        for (const fieldname of ["material_expense_account", "labor_expense_account", "machine_expense_account", "internal_rework_expense_account"]) {
            frm.set_query(fieldname, () => ({filters: {company: frm.doc.company, root_type: "Expense", is_group: 0}}));
        }
        frm.set_query("default_project", () => ({filters: {company: frm.doc.company}}));
    },
    company(frm) {
        if (frm.is_new()) return;
        for (const fieldname of ["customer_cost_center", "internal_rework_cost_center", "material_expense_account", "labor_expense_account", "machine_expense_account", "internal_rework_expense_account", "default_project"]) {
            frm.set_value(fieldname, null);
        }
    },
});
