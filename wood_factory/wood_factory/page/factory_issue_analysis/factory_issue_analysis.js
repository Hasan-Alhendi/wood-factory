frappe.pages["factory-issue-analysis"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Issue Analysis"), single_column: true});
    page.main.addClass("factory-issue-analysis-page");
    page.add_field({label: __("From Date"), fieldname: "from_date", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30), change: () => load_analysis(page)});
    page.add_field({label: __("To Date"), fieldname: "to_date", fieldtype: "Date", default: frappe.datetime.get_today(), change: () => load_analysis(page)});
    page.set_primary_action(__("Refresh"), () => load_analysis(page));
    load_analysis(page);
};

function load_analysis(page) {
    frappe.call({method: "wood_factory.wood_factory.page.factory_issue_analysis.factory_issue_analysis.get_issue_analysis", args: {from_date: page.fields_dict.from_date.get_value(), to_date: page.fields_dict.to_date.get_value()}, freeze: true}).then(r => render_analysis(page, r.message || {}));
}

function render_analysis(page, data) {
    const s = data.summary || {};
    page.main.html(`<div class="issue-kpis">${kpi(__("Stoppages"), s.stoppages)}${kpi(__("Blocked Hours"), s.blocked_hours)}${kpi(__("Piece Exceptions"), s.exceptions)}${kpi(__("Affected Orders"), s.affected_orders)}</div><div class="issue-columns"><section><h3>${__("Stoppage Causes")}</h3>${reason_rows(data.stop_reasons || [])}</section><section><h3>${__("Piece Error Types")}</h3>${reason_rows(data.exception_types || [])}</section></div><section><h3>${__("Issues by Production Stage")}</h3>${stage_rows(data.stages || [])}</section>`);
}

function kpi(label, value) { return `<div class="issue-kpi"><span>${label}</span><b>${value || 0}</b></div>`; }
function reason_rows(rows) { return `<div class="issue-list">${rows.length ? rows.map(row => `<div class="reason-row"><div><b>${__(row.reason)}</b><span>${row.count} ${__("occurrence(s)")}</span></div><strong>${row.percent}%</strong></div>`).join("") : empty()}</div>`; }
function stage_rows(rows) { return `<div class="issue-table"><div class="stage-row header"><b>${__("Stage")}</b><b>${__("Stoppages")}</b><b>${__("Blocked Hours")}</b><b>${__("Exceptions")}</b></div>${rows.map(row => `<div class="stage-row"><span>${__(row.stage)}</span><span>${row.stoppages}</span><span>${(row.blocked_minutes / 60).toFixed(2)}</span><span>${row.exceptions}</span></div>`).join("") || empty()}</div>`; }
function empty() { return `<div class="issue-empty">${__("No issues recorded for this period")}</div>`; }
