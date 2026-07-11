frappe.ui.form.on("Cutting Order", {
    refresh(frm) {
        if (!frm.is_new() && !["Approved", "In Cutting", "Completed", "Cancelled"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Optimize Board Layout"), () => {
                frm.call("optimize_layout").then((r) => {
                    const result = r.message;
                    frappe.show_alert({
                        message: __("Optimized with {0}: {1} board(s), {2}% waste", [result.algorithm, result.board_count, result.waste_percent]),
                        indicator: "green",
                    });
                    frm.reload_doc();
                });
            }, __("Cutting"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Board Layouts"), () => {
                frappe.set_route("List", "Board Layout", { cutting_order: frm.doc.name });
            }, __("View"));
        }
    },
});
