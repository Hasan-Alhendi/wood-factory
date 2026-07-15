frappe.ui.form.on("Factory Workstation", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Preview Queue Rebalancing"), () => preview_rebalance(frm), __("Queue"));
        if (frm.doc.status !== "Active") {
            frm.add_custom_button(__("Rebalance Waiting Queue"), () => rebalance(frm), __("Queue"));
        }
    },
});
function preview_rebalance(frm) {
    frm.call("preview_queue_rebalancing").then(r => {
        const data = r.message || {}, moves = data.moves || [];
        const rows = moves.map(x => `<tr><td>${frappe.utils.escape_html(x.order)}</td><td>${__(x.priority)}</td><td>${frappe.utils.escape_html(x.from_workstation)}</td><td>${frappe.utils.escape_html(x.to_workstation || __("No Capacity"))}</td></tr>`).join("");
        frappe.msgprint({title: __("Queue Rebalancing Preview"), wide: true, message: `<p>${__("Waiting jobs")}: <b>${data.waiting_jobs || 0}</b> · ${__("Movable")}: <b>${data.movable || 0}</b></p><table class="table table-bordered"><thead><tr><th>${__("Order")}</th><th>${__("Priority")}</th><th>${__("From")}</th><th>${__("Suggested Workstation")}</th></tr></thead><tbody>${rows || `<tr><td colspan="4">${__("No queue changes suggested")}</td></tr>`}</tbody></table>`});
    });
}
function rebalance(frm) {
    frappe.confirm(__("Move waiting jobs to the best active workstations? In-progress work will never be moved."), () => frm.call("rebalance_waiting_queue").then(r => { frappe.show_alert({message: __("Moved {0} waiting job(s)", [(r.message || {}).moved || 0]), indicator: "green"}); frm.reload_doc(); }));
}
