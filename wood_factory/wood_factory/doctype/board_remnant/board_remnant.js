frappe.ui.form.on("Board Remnant", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frm.doc.status === "Available") {
            frm.add_custom_button(__("Reserve for Piece"), () => reserve_remnant(frm), __("Remnant"));
            frm.add_custom_button(__("Scrap Remnant"), () => run_remnant_method(frm, "scrap"), __("Remnant"));
        }
        if (frm.doc.status === "Reserved") {
            frm.add_custom_button(__("Consume"), () => run_remnant_method(frm, "consume"), __("Remnant"));
            frm.add_custom_button(__("Release Reservation"), () => run_remnant_method(frm, "release_reservation"), __("Remnant"));
        }
    },
});

function run_remnant_method(frm, method, args = {}) { frm.call(method, args).then(() => frm.reload_doc()); }
function reserve_remnant(frm) {
    frappe.prompt([{fieldname: "factory_piece", fieldtype: "Link", options: "Factory Piece", label: __("Replacement Piece"), reqd: 1, get_query: () => ({filters: {is_exception: 1, status: ["!=", "Completed"]}})}], values => {
        run_remnant_method(frm, "reserve_for_piece", values);
    }, __("Reserve Remnant"), __("Reserve"));
}
