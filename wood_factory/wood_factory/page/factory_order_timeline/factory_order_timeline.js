frappe.pages["factory-order-timeline"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Order Timeline"), single_column: true});
    page.main.addClass("factory-order-timeline-page");
    page.add_field({label: __("Factory Order"), fieldname: "factory_order", fieldtype: "Link", options: "Factory Order", reqd: 1, change: () => load_timeline(page)});
    const route = frappe.get_route();
    if (route[1]) page.fields_dict.factory_order.set_value(route[1]);
};

function load_timeline(page) {
    const factory_order = page.fields_dict.factory_order.get_value();
    if (!factory_order) return page.main.empty();
    frappe.call({method: "wood_factory.wood_factory.page.factory_order_timeline.factory_order_timeline.get_order_timeline", args: {factory_order}, freeze: true}).then(r => render_timeline(page, r.message || {}));
}

function render_timeline(page, data) {
    const order = data.order || {}, events = data.events || [];
    page.main.html(`<div class="timeline-summary"><div><h2>${order.name || ""}</h2><span>${frappe.utils.escape_html(order.customer || "")}</span></div><div><b>${__(order.current_stage || order.status || "")}</b><span>${order.progress_percent || 0}%</span></div></div><div class="factory-timeline"></div>`);
    const box = page.main.find(".factory-timeline");
    events.forEach(event => box.append(`<div class="timeline-event event-${frappe.scrub(event.event_type)}"><div class="timeline-dot"></div><div class="timeline-card"><div class="timeline-head"><b>${__(event.event_type)}</b><time>${frappe.datetime.str_to_user(event.event_at)}</time></div><h4>${__(event.stage || "Factory Order")}</h4><div>${frappe.utils.escape_html(event.details || "")}</div>${event.reason ? `<div class="timeline-reason"><b>${__("Reason")}:</b> ${frappe.utils.escape_html(event.reason)}</div>` : ""}<small>${__("By")}: ${frappe.utils.escape_html(event.performed_by || "")}</small></div></div>`));
    if (!events.length) box.html(`<div class="text-muted timeline-empty">${__("No production events recorded yet")}</div>`);
}
