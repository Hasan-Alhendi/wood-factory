frappe.pages["factory-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Dashboard"), single_column: true});
    page.main.addClass("factory-dashboard-page");
    page.set_primary_action(__("Refresh"), () => load_dashboard(page));
    page.add_inner_button(__("Worker Screen"), () => frappe.set_route("factory-worker"));
    page.add_inner_button(__("Performance"), () => frappe.set_route("factory-performance"));
    load_dashboard(page);
    page.factory_refresh = setInterval(() => load_dashboard(page, false), 60000);
    $(wrapper).on("remove", () => clearInterval(page.factory_refresh));
};

function load_dashboard(page, freeze = true) {
    frappe.call({method: "wood_factory.wood_factory.page.factory_dashboard.factory_dashboard.get_dashboard_data", freeze}).then(r => render_dashboard(page, r.message || {}));
}

function render_dashboard(page, data) {
    page.main.empty();
    const s = data.summary || {};
    page.main.append(`<div class="factory-kpis">${kpi(__("Active Orders"), s.active_orders)}${kpi(__("Needs Intervention"), s.needs_intervention, "danger")}${kpi(__("Delayed"), s.delayed_orders, "danger")}${kpi(__("Blocked"), s.blocked_orders, "warning")}${kpi(__("Open Exceptions"), s.open_exceptions, "warning")}${kpi(__("Ready for Delivery"), s.ready_for_delivery, "success")}</div>`);
    page.main.append(section(__("Needs Management Intervention"), intervention_rows(data.intervention_alerts || [])));
    page.main.append(`<h3>${__("Orders by Current Stage")}</h3><div class="stage-board"></div>`);
    const stages = page.main.find(".stage-board");
    Object.entries(data.stage_counts || {}).forEach(([stage, count]) => stages.append(`<button class="stage-tile" data-stage="${frappe.utils.escape_html(stage)}"><span>${__(stage)}</span><b>${count}</b></button>`));
    page.main.append(section(__("Delayed Orders"), delayed_rows(data.delayed_orders || [])));
    page.main.append(section(__("Blocked Work"), blocked_rows(data.blocked_stages || [])));
    page.main.append(section(__("Open Piece Exceptions"), exception_rows(data.exceptions || [])));
    page.main.find(".stage-tile").on("click", function () { frappe.route_options = {current_stage: $(this).data("stage")}; frappe.set_route("List", "Factory Order"); });
    page.main.find("[data-order]").on("click", function () { frappe.set_route("Form", "Factory Order", $(this).data("order")); });
    page.main.find("[data-exception]").on("click", function () { frappe.set_route("Form", "Piece Exception", $(this).data("exception")); });
    page.main.find("[data-reference-type]").on("click", function () { frappe.set_route("Form", $(this).data("reference-type"), $(this).data("reference-name")); });
}

function kpi(label, value, tone = "") { return `<div class="factory-kpi ${tone}"><span>${label}</span><b>${value || 0}</b></div>`; }
function section(title, rows) { return `<section class="dashboard-section"><h3>${title}</h3><div class="dashboard-list">${rows || `<div class="dashboard-empty">${__("Nothing to show")}</div>`}</div></section>`; }
function intervention_rows(rows) { return rows.map(row => `<button class="dashboard-row intervention-${row.priority.toLowerCase()}" data-reference-type="${row.reference_type}" data-reference-name="${row.reference_name}"><b>${__(row.priority)} · ${__(row.alert_type)}</b><span>${row.reference_name}</span><span>${frappe.utils.escape_html(row.description || "")}</span><strong>${frappe.utils.escape_html(row.responsible || __("Administrator"))}</strong></button>`).join(""); }
function delayed_rows(rows) { return rows.map(row => `<button class="dashboard-row" data-order="${row.name}"><b>${row.name}</b><span>${frappe.utils.escape_html(row.customer || "")}</span><span>${__(row.current_stage || "")}</span><strong>${row.computed_delay_days} ${__("days late")}</strong></button>`).join(""); }
function blocked_rows(rows) { return rows.map(row => `<button class="dashboard-row" data-order="${row.parent}"><b>${row.parent}</b><span>${__(row.stage)}</span><span>${frappe.utils.escape_html(row.block_reason || "")}</span><strong>${frappe.utils.escape_html(row.responsible || "")}</strong></button>`).join(""); }
function exception_rows(rows) { return rows.map(row => `<button class="dashboard-row" data-exception="${row.name}"><b>${row.factory_order}</b><span>${__(row.exception_type)}</span><span>${__(row.reported_stage || "")}</span><strong>${__(row.status)}</strong></button>`).join(""); }
