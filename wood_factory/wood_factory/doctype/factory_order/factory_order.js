frappe.ui.form.on("Factory Order", {
    refresh(frm) {
        if (!frm.is_new() && !(frm.doc.production_stages || []).length) {
            frm.add_custom_button(__("Initialize Production Stages"), () => run_order_method(frm, "initialize_production_stages"), __("Production"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Factory Pieces"), () => frappe.set_route("List", "Factory Piece", {factory_order: frm.doc.name}), __("View"));
        }
        const active = (frm.doc.production_stages || []).find(row => ["Ready", "In Progress", "Blocked"].includes(row.status));
        if (!active) return;
        if (["Ready", "Blocked"].includes(active.status)) {
            frm.add_custom_button(__("Start / Resume: {0}", [active.stage]), () => run_stage_method(frm, "start_stage", active), __("Production"));
        }
        if (active.status === "In Progress") {
            frm.add_custom_button(__("Complete: {0}", [active.stage]), () => run_stage_method(frm, "complete_stage", active), __("Production"));
            frm.add_custom_button(__("Block: {0}", [active.stage]), () => block_stage(frm, active), __("Production"));
        }
    },
});

function run_order_method(frm, method) { frm.call(method).then(() => frm.reload_doc()); }
function run_stage_method(frm, method, row) {
    frm.call(method, {row_name: row.name}).then(() => { frappe.show_alert({message: __("Production stage updated"), indicator: "green"}); frm.reload_doc(); });
}
function block_stage(frm, row) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {row_name: row.name, reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Production Stage"), __("Block"));
}
