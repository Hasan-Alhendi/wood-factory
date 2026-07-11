frappe.pages["factory-schedule"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Production Schedule"), single_column: true});
    page.main.addClass("factory-schedule-page"); page.set_primary_action(__("Refresh Queue"), () => load_schedule(page)); load_schedule(page);
};
function load_schedule(page) { frappe.call({method:"wood_factory.wood_factory.page.factory_schedule.factory_schedule.get_production_schedule", freeze:true}).then(r => render_schedule(page, r.message || {})); }
function render_schedule(page, data) {
    const s=data.summary||{}, rows=data.orders||[];
    page.main.html(`<div class="schedule-kpis">${kpi(__("Queued Orders"),s.queued)}${kpi(__("Urgent"),s.urgent,"urgent")}${kpi(__("At Risk / Late"),s.at_risk,"high")}${kpi(__("Unassigned"),s.unassigned,"warning")}</div><div class="schedule-list">${rows.map(order=>`<button class="schedule-row priority-${(order.priority||"normal").toLowerCase()}" data-order="${order.name}"><strong class="queue-number">#${order.queue_position}</strong><div><b>${order.name}</b><span>${frappe.utils.escape_html(order.customer||"")}</span></div><div><b>${__(order.priority)}</b><span>${order.priority_override?__("Manual override"):__("Automatic priority")}</span></div><div><b>${__(order.current_stage||order.status)}</b><span>${order.workstation?frappe.utils.escape_html(order.workstation):__("Workstation not assigned")}</span></div><div><b>${eta_text(order)}</b><span class="eta-risk-${slug(order.eta_risk)}">${__(order.eta_risk||"No Forecast")}</span></div><div><b>${delivery_text(order)}</b><span>${order.open_exceptions} ${__("open exception(s)")}</span></div></button>`).join("")||`<div class="schedule-empty">${__("No orders waiting for production")}</div>`}</div>`);
    page.main.find("[data-order]").on("click",function(){frappe.set_route("Form","Factory Order",$(this).data("order"));});
}
function kpi(label,value,tone=""){return `<div class="schedule-kpi ${tone}"><span>${label}</span><b>${value||0}</b></div>`;}
function delivery_text(order){if(order.computed_delay_days)return `${order.computed_delay_days} ${__("days late")}`;if(order.days_left===null)return __("No delivery date");return order.days_left===0?__("Due today"):`${order.days_left} ${__("days left")}`;}
function eta_text(order){return order.estimated_completion?`${__("ETA")}: ${frappe.datetime.str_to_user(order.estimated_completion)}`:__("ETA unavailable");}
function slug(value){return (value||"").toLowerCase().replaceAll(" ","-");}
