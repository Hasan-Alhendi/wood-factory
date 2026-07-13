frappe.ui.form.on("Cutting Order", {
    refresh(frm) {
        if (!frm.is_new() && !["Approved", "In Cutting", "Completed", "Cancelled"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Optimize Board Layout"), () => {
                frm.call("optimize_layout").then((r) => {
                    const result = r.message;
                    frappe.show_alert({message: __("Optimized with {0}: {1} board(s), {2}% waste", [result.algorithm, result.board_count, result.waste_percent]), indicator: "green"});
                    frm.reload_doc();
                });
            }, __("Cutting"));
        }
        if (frm.doc.status === "Optimized" && !frm.doc.material_stock_entry) {
            frm.add_custom_button(__("Check Material Stock"), () => show_material_availability(frm), __("Materials"));
            frm.add_custom_button(__("Approve & Consume Materials"), () => approve_and_consume(frm), __("Materials"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Board Layouts"), () => frappe.set_route("List", "Board Layout", {cutting_order: frm.doc.name}), __("View"));
        }
        if (frm.doc.material_stock_entry) {
            frm.add_custom_button(__("Material Stock Entry"), () => frappe.set_route("Form", "Stock Entry", frm.doc.material_stock_entry), __("View"));
        }
        if (frm.doc.cost_ledger_entry) {
            frm.add_custom_button(__("Factory Cost Ledger"), () => frappe.set_route("Form", "Factory Cost Ledger", frm.doc.cost_ledger_entry), __("View"));
        }
    },
});

function show_material_availability(frm) {
    frm.call("check_material_availability").then((r) => {
        const result = r.message;
        const rows = result.requirements.map(row => `<tr><td>${frappe.utils.escape_html(row.item_code)}</td><td>${row.qty} ${row.uom}</td><td>${row.available_qty} ${row.uom}</td><td>${row.shortage_qty || "—"}</td><td>${frappe.utils.escape_html(row.warehouse)}</td></tr>`).join("");
        const indicator = result.has_shortage ? "red" : "green";
        const message = result.has_shortage ? __("Material shortage found") : __("All required materials are available");
        frappe.msgprint({title: message, indicator, message: `<table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Required")}</th><th>${__("Available Qty")}</th><th>${__("Shortage")}</th><th>${__("Warehouse")}</th></tr></thead><tbody>${rows}</tbody></table>`});
    });
}

function approve_and_consume(frm) {
    const owner = frm.doc.order_type === "Internal Replacement" ? __("the factory internal rework cost center") : __("the customer order cost center");
    frappe.confirm(__("This will submit a Material Issue, deduct boards and edge band from stock, and post the value to {0}. Continue?", [owner]), () => {
        frm.call("approve_and_consume_materials").then((r) => {
            const result = r.message || {};
            const billable = result.customer_billable ? __("Customer order cost") : __("Factory internal rework cost");
            frappe.msgprint({
                title: __("Materials Posted"),
                indicator: "green",
                message: `<p>${__("Stock Entry")}: <b>${frappe.utils.escape_html(result.stock_entry || "")}</b></p><p>${__("Posted Value")}: <b>${result.posted_value || 0} ${frappe.utils.escape_html(result.currency || "")}</b></p><p>${__("Cost Owner")}: <b>${billable}</b></p>`,
            });
            frm.reload_doc();
        });
    });
}
