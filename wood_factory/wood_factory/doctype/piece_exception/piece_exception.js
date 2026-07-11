frappe.ui.form.on("Piece Exception", {
    refresh(frm) {
        if (frm.is_new() || ["Resolved", "Cancelled"].includes(frm.doc.status)) return;
        if (!["Replacement Required", "Replacement In Production", "Replacement Completed"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Require Replacement"), () => run_exception_method(frm, "require_replacement"), __("Replacement"));
        }
        if (frm.doc.status === "Replacement Required") {
            frm.add_custom_button(__("Start Replacement Manufacturing"), () => run_exception_method(frm, "start_replacement"), __("Replacement"));
        }
        if (frm.doc.status === "Replacement In Production" && frm.doc.replacement_piece) {
            frm.add_custom_button(__("Find Best Remnant"), () => find_best_remnant(frm), __("Replacement"));
            frm.add_custom_button(__("Open Replacement Piece"), () => frappe.set_route("Form", "Factory Piece", frm.doc.replacement_piece), __("Replacement"));
            frm.add_custom_button(__("Confirm Replacement Completed"), () => run_exception_method(frm, "confirm_replacement_completed"), __("Replacement"));
        }
        if (frm.doc.suggested_remnant) {
            frm.add_custom_button(__("Open Suggested Remnant"), () => frappe.set_route("Form", "Board Remnant", frm.doc.suggested_remnant), __("Replacement"));
        }
        if (frm.doc.status === "Replacement Completed") {
            frm.add_custom_button(__("Open Replacement Piece"), () => frappe.set_route("Form", "Factory Piece", frm.doc.replacement_piece), __("Replacement"));
        }
        frm.add_custom_button(__("Resolve Exception"), () => close_exception(frm, "resolve", __("Resolution Notes")), __("Exception"));
        if (!frm.doc.replacement_piece) frm.add_custom_button(__("Cancel Exception"), () => close_exception(frm, "cancel_exception", __("Cancellation Notes")), __("Exception"));
    },
});

function run_exception_method(frm, method, args = {}) { return frm.call(method, args).then(() => frm.reload_doc()); }
function find_best_remnant(frm) {
    frm.call("find_best_remnant").then(r => {
        const result = r.message || {};
        if (result.found) frappe.show_alert({message: __(`Reserved remnant ${result.remnant} with ${result.waste_area_m2} m² remaining area`), indicator: "green"});
        else frappe.msgprint(__(`No available remnant of board item ${result.board_item} fits this replacement piece.`));
        return frm.reload_doc();
    });
}
function close_exception(frm, method, label) {
    frappe.prompt([{fieldname: "resolution_notes", fieldtype: "Small Text", label, reqd: 1}], values => run_exception_method(frm, method, values), label, __("Confirm"));
}
