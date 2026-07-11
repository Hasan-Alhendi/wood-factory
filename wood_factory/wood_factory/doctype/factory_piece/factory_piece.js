frappe.ui.form.on("Factory Piece", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (!frm.doc.is_exception && frm.doc.status !== "Completed") {
            frm.add_custom_button(__("Report Missing / Damaged"), () => report_exception(frm), __("Exception"));
            return;
        }
        if (!frm.doc.is_exception) return;
        frm.add_custom_button(__("Open Exception"), () => frappe.set_route("List", "Piece Exception", {factory_piece: frm.doc.name}), __("Exception"));
        if (frm.doc.status === "Completed") return;
        if (["Ready", "Blocked"].includes(frm.doc.status)) frm.add_custom_button(__("Start / Resume"), () => run_piece_method(frm, "start_stage"), __("Production"));
        if (frm.doc.status === "In Progress") {
            frm.add_custom_button(__("Complete Stage"), () => run_piece_method(frm, "complete_stage"), __("Production"));
            frm.add_custom_button(__("Block"), () => block_piece(frm), __("Production"));
        }
    },
});

function run_piece_method(frm, method) { frm.call(method).then(() => frm.reload_doc()); }
function report_exception(frm) {
    frappe.prompt([
        {fieldname: "exception_type", fieldtype: "Select", label: __("Exception Type"), options: "Missing\nDamaged\nWrong Dimensions\nWrong Edge Banding\nQuality Rejection\nDelayed\nOther", reqd: 1},
        {fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1},
    ], values => {
        frappe.new_doc("Piece Exception", {factory_piece: frm.doc.name, exception_type: values.exception_type, reason: values.reason});
    }, __("Report Piece Exception"), __("Create"));
}
function block_piece(frm) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Piece"), __("Block"));
}
