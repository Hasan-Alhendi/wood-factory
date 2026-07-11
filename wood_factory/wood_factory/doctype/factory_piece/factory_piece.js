frappe.ui.form.on("Factory Piece", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.status === "Completed") return;
        if (["Ready", "Blocked"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Start / Resume"), () => run_piece_method(frm, "start_stage"), __("Production"));
        }
        if (frm.doc.status === "In Progress") {
            frm.add_custom_button(__("Complete Stage"), () => run_piece_method(frm, "complete_stage"), __("Production"));
            frm.add_custom_button(__("Block"), () => block_piece(frm), __("Production"));
        }
    },
});

function run_piece_method(frm, method) {
    frm.call(method).then(() => frm.reload_doc());
}

function block_piece(frm) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Piece"), __("Block"));
}
