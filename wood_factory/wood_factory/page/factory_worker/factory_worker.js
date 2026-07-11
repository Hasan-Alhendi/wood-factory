frappe.pages["factory-worker"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Worker"), single_column: true});
    page.set_primary_action(__("Refresh"), () => load_queue(page));
    page.add_inner_button(__("Scan QR / Barcode"), () => frappe.set_route("factory-scan"));
    page.add_field({label: __("Stage"), fieldname: "stage", fieldtype: "Select", options: "\nCutting\nEdge Banding\nDrilling\nAssembly\nQuality Inspection\nPacking", change: () => { page.fields_dict.workstation.set_value(""); load_queue(page); }});
    page.add_field({label: __("Workstation"), fieldname: "workstation", fieldtype: "Link", options: "Factory Workstation", get_query: () => ({filters: {status: "Active", ...(page.fields_dict.stage.get_value() ? {stage: page.fields_dict.stage.get_value()} : {})}}), change: () => load_queue(page)});
    page.main.addClass("factory-worker-page"); load_queue(page);
};
function load_queue(page) {
    const stage = page.fields_dict.stage.get_value(), workstation = page.fields_dict.workstation.get_value();
    frappe.call({method: "wood_factory.wood_factory.page.factory_worker.factory_worker.get_worker_queue", args: {stage, workstation}, freeze: true}).then(r => render_queue(page, r.message || {}));
}
function render_queue(page, data) {
    page.main.empty(); const orders = data.orders || [], exceptions = data.exceptions || [];
    page.main.append(`<div class="worker-summary"><b>${data.workstation ? `${__("Workstation")}: ${frappe.utils.escape_html(data.workstation)}` : __("All stage work")}</b><span>${__("Whole orders")}: ${orders.length}</span><span>${__("Separate pieces")}: ${exceptions.length}</span></div>`);
    page.main.append(`<h3>${data.workstation ? __("Workstation Queue") : __("Whole Factory Orders")}</h3><div class="worker-orders"></div>`);
    const orderBox = page.main.find(".worker-orders"); orders.forEach(order => orderBox.append(order_card(order)));
    if (!orders.length) orderBox.append(`<div class="text-muted worker-empty">${__("No whole orders waiting in this queue")}</div>`);
    page.main.append(`<h3 class="worker-section">${__("Exception Pieces Only")}</h3><div class="worker-pieces"></div>`);
    const pieceBox = page.main.find(".worker-pieces"); exceptions.forEach(piece => pieceBox.append(piece_card(piece)));
    if (!exceptions.length) pieceBox.append(`<div class="text-muted worker-empty">${__("No pieces require separate tracking")}</div>`);
    bind_actions(page);
}
function order_card(order) {
    return `<div class="worker-card ${order.queue_position===1?"queue-next":""}" data-kind="order" data-name="${frappe.utils.escape_html(order.name)}"><strong class="worker-position">#${order.queue_position}</strong><div class="worker-card-body"><h4>${order.name}</h4><div>${frappe.utils.escape_html(order.customer || "")} · <b>${__(order.current_stage || "")}</b></div><small>${frappe.utils.escape_html(order.workstation || __("Unassigned"))} · ${__(order.priority || "Normal")} · ${__("Stage Status")}: ${__(order.stage_status)}${order.delay_days ? ` · ${__("Delayed")} ${order.delay_days} ${__("days")}` : ""}</small></div>${action_buttons(order.stage_status)}</div>`;
}
function piece_card(piece) { return `<div class="worker-card worker-exception" data-kind="piece" data-name="${frappe.utils.escape_html(piece.name)}"><div class="worker-card-body"><h4>${frappe.utils.escape_html(piece.part_name || piece.piece_uid)}</h4><div>${piece.factory_order} · ${piece.width_mm} × ${piece.height_mm} mm · <b>${__(piece.current_stage)}</b></div><small>${__("Separate piece")}: ${__(piece.status)}${piece.block_reason ? ` · ${frappe.utils.escape_html(piece.block_reason)}` : ""}</small></div>${action_buttons(piece.status)}</div>`; }
function action_buttons(status) { if (["Ready", "Blocked"].includes(status)) return `<button class="btn btn-primary worker-action" data-action="start">${__("Start")}</button>`; if (status === "In Progress") return `<div class="worker-actions"><button class="btn btn-danger worker-action" data-action="block">${__("Block")}</button><button class="btn btn-primary worker-action" data-action="complete">${__("Complete Stage")}</button></div>`; return ""; }
function bind_actions(page) { page.main.find(".worker-action").on("click", function () { const card=$(this).closest(".worker-card"),kind=card.data("kind"),name=card.data("name"),action=$(this).data("action"); if(action==="block") frappe.prompt([{fieldname:"reason",fieldtype:"Small Text",label:__("Block Reason"),reqd:1}],values=>run_action(page,kind,name,action,values.reason),__("Block Work"),__("Confirm")); else run_action(page,kind,name,action); }); }
function run_action(page, kind, name, action, reason=null) { const method=kind==="order"?"run_order_action":"run_piece_action", workstation=page.fields_dict.workstation.get_value(); frappe.call({method:`wood_factory.wood_factory.page.factory_worker.factory_worker.${method}`,args:{[kind]:name,action,reason,...(kind==="order"?{workstation}: {})},freeze:true}).then(()=>load_queue(page)); }
