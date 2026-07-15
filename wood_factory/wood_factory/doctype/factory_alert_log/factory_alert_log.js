frappe.ui.form.on("Factory Alert Log", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (!["Acknowledged", "Resolved"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Acknowledge"), () => frm.call("acknowledge").then(() => frm.reload_doc()), __("Alert"));
        }
        if (frm.doc.status !== "Resolved") {
            frm.add_custom_button(__("Resolve"), () => frappe.confirm(__("Resolve this alert manually?"), () => frm.call("resolve_alert").then(() => frm.reload_doc())), __("Alert"));
        }
        if (frm.doc.reference_doctype && frm.doc.reference_name) {
            frm.add_custom_button(__("Open Reference"), () => frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name), __("View"));
        }
    },
});
