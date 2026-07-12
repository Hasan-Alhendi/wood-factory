frappe.ui.form.on("Factory Order", {
    setup(frm) {
        frm.set_query("cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("rework_cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("project", () => ({filters: {company: frm.doc.company}}));
    },
    refresh(frm) {
        if (!frm.is_new() && !(frm.doc.production_stages || []).length) {
            frm.add_custom_button(__("Initialize Production Stages"), () => run_order_method(frm, "initialize_production_stages"), __("Production"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Factory Pieces"), () => frappe.set_route("List", "Factory Piece", {factory_order: frm.doc.name}), __("View"));
            frm.add_custom_button(__("Production Timeline"), () => frappe.set_route("factory-order-timeline", frm.doc.name), __("View"));
            frm.add_custom_button(__("Cutting Orders"), () => frappe.set_route("List", "Cutting Order", {factory_order: frm.doc.name}), __("View"));
            frm.add_custom_button(__("Factory Cost Ledger"), () => frappe.set_route("List", "Factory Cost Ledger", {factory_order: frm.doc.name}), __("Accounting"));
        }
        if (frappe.user.has_role("System Manager") || frappe.user.has_role("Accounts Manager")) {
            frm.add_custom_button(__("Accounting Settings"), () => frappe.set_route("Form", "Factory Accounting Settings"), __("Accounting"));
        }
        const active = (frm.doc.production_stages || []).find(row => ["Ready", "In Progress", "Blocked"].includes(row.status));
        if (!active) return;
        if (["Ready", "Blocked"].includes(active.status)) {
            frm.add_custom_button(__("Auto Assign Workstation: {0}", [active.stage]), () => run_stage_method(frm, "auto_assign_stage", active), __("Production"));
            frm.add_custom_button(__("Start / Resume: {0}", [active.stage]), () => run_stage_method(frm, "start_stage", active), __("Production"));
        }
        if (active.status === "In Progress") {
            frm.add_custom_button(__("Complete: {0}", [active.stage]), () => run_stage_method(frm, "complete_stage", active), __("Production"));
            frm.add_custom_button(__("Block: {0}", [active.stage]), () => block_stage(frm, active), __("Production"));
        }
    },
});

frappe.ui.form.on("Factory Order Stage", {
    workstation(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.workstation || !row.stage) return;
        frappe.db.get_value("Factory Workstation", row.workstation, ["stage", "status"]).then(r => {
            const workstation = r.message || {};
            if (workstation.stage && workstation.stage !== row.stage) {
                frappe.msgprint(__("This workstation belongs to {0}, not {1}", [workstation.stage, row.stage]));
                frappe.model.set_value(cdt, cdn, "workstation", null);
            } else if (workstation.status && workstation.status !== "Active") {
                frappe.msgprint(__("Selected workstation is not active"));
            }
        });
    },
});

function run_order_method(frm, method) { frm.call(method).then(() => frm.reload_doc()); }
function run_stage_method(frm, method, row) {
    frm.call(method, {row_name: row.name}).then(r => { const workstation = r.message && r.message.workstation; frappe.show_alert({message: workstation ? __("Assigned to {0}", [workstation]) : __("Production stage updated"), indicator: "green"}); frm.reload_doc(); });
}
function block_stage(frm, row) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {row_name: row.name, reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Production Stage"), __("Block"));
}
