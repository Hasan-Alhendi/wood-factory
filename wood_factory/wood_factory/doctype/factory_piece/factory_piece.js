frappe.ui.form.on("Factory Piece", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (!frm.doc.is_exception && frm.doc.status !== "Completed") {
            frm.add_custom_button(__("Track Separately"), () => mark_exception(frm), __("Exception"));
            return;
        }
        if (!frm.doc.is_exception) return;
        frm.add_custom_button(__("Return to Order Flow"), () => run_piece_method(frm, "return_to_order_flow"), __("Exception"));
        if (frm.doc.status === "Completed") return;
        if (["Ready", "Blocked"].includes(frm.doc.status)) frm.add_custom_button(__("Start / Resume"), () => run_piece_method(frm, "start_stage"), __("Production"));
        if (frm.doc.status === "In Progress") {
            frm.add_custom_button(__("Complete Stage"), () => run_piece_method(frm, "complete_stage"), __("Production"));
            frm.add_custom_button(__("Block"), () => block_piece(frm), __("Production"));
        }
    },
});

function run_piece_method(frm, method) { frm.call(method).then(() => frm.reload_doc()); }
function mark_exception(frm) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Why is this piece tracked separately?"), reqd: 1}], values => {
        frm.call("track_separately", {reason: values.reason}).then(() => frm.reload_doc());
    }, __("Track Piece Separately"), __("Confirm"));
}
function block_piece(frm) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Piece"), __("Block"));
}
