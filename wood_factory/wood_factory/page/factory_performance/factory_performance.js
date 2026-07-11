frappe.pages["factory-performance"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Performance"), single_column: true});
    page.main.addClass("factory-performance-page");
    page.add_field({label: __("From Date"), fieldname: "from_date", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30), change: () => load_performance(page)});
    page.add_field({label: __("To Date"), fieldname: "to_date", fieldtype: "Date", default: frappe.datetime.get_today(), change: () => load_performance(page)});
    page.set_primary_action(__("Refresh"), () => load_performance(page));
    load_performance(page);
};

function load_performance(page) {
    frappe.call({method: "wood_factory.wood_factory.page.factory_performance.factory_performance.get_performance_data", args: {from_date: page.fields_dict.from_date.get_value(), to_date: page.fields_dict.to_date.get_value()}, freeze: true}).then(r => render_performance(page, r.message || {}));
}

function render_performance(page, data) {
    const s = data.summary || {};
    page.main.html(`<div class="performance-kpis">${kpi(__("Orders Measured"), s.completed_orders)}${kpi(__("Completed Stages"), s.completed_stages)}${kpi(__("Actual Work Hours"), s.work_hours)}${kpi(__("Blocked Hours"), s.blocked_hours)}</div><section><h3>${__("Stage Performance")}</h3><div class="performance-table">${stage_rows(data.stages || [])}</div></section><section><h3>${__("Likely Bottlenecks")}</h3><div class="bottleneck-grid">${bottleneck_rows(data.bottlenecks || [])}</div></section><section><h3>${__("Worker Activity")}</h3><div class="performance-table">${worker_rows(data.workers || [])}</div></section>`);
}

function kpi(label, value) { return `<div class="performance-kpi"><span>${label}</span><b>${value || 0}</b></div>`; }
function stage_rows(rows) { return `<div class="performance-row header"><b>${__("Stage")}</b><b>${__("Completed")}</b><b>${__("Avg. Minutes")}</b><b>${__("Blocked %")}</b></div>` + rows.map(row => `<div class="performance-row"><span>${__(row.stage)}</span><span>${row.completed}</span><span>${row.avg_minutes}</span><span>${row.blocked_percent}%</span></div>`).join(""); }
function bottleneck_rows(rows) { return rows.length ? rows.map((row, index) => `<div class="bottleneck-card"><small>#${index + 1}</small><h4>${__(row.stage)}</h4><b>${row.avg_minutes} ${__("min avg")}</b><span>${row.blocked_percent}% ${__("blocked")}</span></div>`).join("") : `<div class="performance-empty">${__("Not enough completed production data yet")}</div>`; }
function worker_rows(rows) { return `<div class="performance-row header"><b>${__("Worker")}</b><b>${__("Completed Stages")}</b><b>${__("Work Hours")}</b><b>${__("Blocked Hours")}</b></div>` + rows.map(row => `<div class="performance-row"><span>${frappe.utils.escape_html(row.user)}</span><span>${row.completed_stages}</span><span>${(row.work_minutes / 60).toFixed(2)}</span><span>${(row.blocked_minutes / 60).toFixed(2)}</span></div>`).join(""); }
