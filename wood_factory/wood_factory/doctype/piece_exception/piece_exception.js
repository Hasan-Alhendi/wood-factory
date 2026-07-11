frappe.ui.form.on("Piece Exception", {
    refresh(frm) {
        if (frm.is_new() || ["Resolved", "Cancelled"].includes(frm.doc.status)) return;
        frm.add_custom_button(__("Require Replacement"), () => run_exception_method(frm, "require_replacement"), __("Exception"));
        frm.add_custom_button(__("Resolve & Return to Order"), () => close_exception(frm, "resolve", __("Resolution Notes")), __("Exception"));
        frm.add_custom_button(__("Cancel Exception"), () => close_exception(frm, "cancel_exception", __("Cancellation Notes")), __("Exception"));
    },
});

function run_exception_method(frm, method, args = {}) {
    frm.call(method, args).then(() => frm.reload_doc());
}

function close_exception(frm, method, label) {
    frappe.prompt([{fieldname: "resolution_notes", fieldtype: "Small Text", label, reqd: 1}], values => {
        run_exception_method(frm, method, values);
    }, label, __("Confirm"));
}
