frappe.pages["factory-reports"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Reports"), single_column: true});
    page.main.addClass("factory-reports-page");
    page.add_field({label: __("From Date"), fieldname: "from_date", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30), change: () => load_reports(page)});
    page.add_field({label: __("To Date"), fieldname: "to_date", fieldtype: "Date", default: frappe.datetime.get_today(), change: () => load_reports(page)});
    page.add_field({label: __("Company"), fieldname: "company", fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company"), change: () => load_reports(page)});
    page.add_field({label: __("Customer"), fieldname: "customer", fieldtype: "Link", options: "Customer", change: () => load_reports(page)});
    page.add_field({label: __("Order Status"), fieldname: "status", fieldtype: "Select", options: "\nNew\nConfirmed\nWaiting for Materials\nReady for Production\nIn Production\nQuality Inspection\nRework\nPacking\nReady for Delivery\nDelivered\nClosed\nCancelled", change: () => load_reports(page)});
    page.set_primary_action(__("Refresh"), () => load_reports(page));
    page.add_inner_button(__("Profitability Report"), () => open_native_report(page, "Factory Order Profitability", true), __("Detailed Reports"));
    page.add_inner_button(__("Waste Analysis"), () => open_native_report(page, "Factory Waste Analysis", true), __("Detailed Reports"));
    page.add_inner_button(__("Production Performance"), () => open_native_report(page, "Factory Production Performance", false), __("Detailed Reports"));
    page.add_inner_button(__("Factory Cost Ledger"), () => frappe.set_route("List", "Factory Cost Ledger"));
    load_reports(page);
};

function report_filters(page) {
    return {
        from_date: page.fields_dict.from_date.get_value(),
        to_date: page.fields_dict.to_date.get_value(),
        company: page.fields_dict.company.get_value(),
        customer: page.fields_dict.customer.get_value(),
        status: page.fields_dict.status.get_value(),
    };
}

function load_reports(page) {
    const filters = report_filters(page);
    if (!filters.company) {
        page.main.html(`<div class="reports-empty">${__("Select a Company to calculate financial reports in one currency")}</div>`);
        return;
    }
    frappe.call({
        method: "wood_factory.wood_factory.page.factory_reports.factory_reports.get_reports",
        args: filters,
        freeze: true,
    }).then(r => render_reports(page, r.message || {}));
}

function open_native_report(page, report_name, include_status) {
    const filters = report_filters(page);
    if (!include_status) delete filters.status;
    frappe.set_route("query-report", report_name, filters);
}

function render_reports(page, data) {
    const f = data.financial || {}, o = data.operations || {}, os = o.summary || {}, w = data.waste || {}, ws = w.summary || {};
    const currency = data.currency || "USD";
    page.main.html(`
        <div class="reports-period">${__("Reporting period")}: <b>${data.period ? data.period.from_date : "-"}</b> → <b>${data.period ? data.period.to_date : "-"}</b> · ${frappe.utils.escape_html((data.filters || {}).company || "")}</div>
        <div class="reports-kpis">
            ${kpi(__("Net Sales"), money(f.revenue, currency))}
            ${kpi(__("Recorded Actual Cost"), money(f.total_actual_cost, currency))}
            ${kpi(__("Profit Before Factory Errors"), money(f.profit_before_factory_errors, currency), f.profit_before_factory_errors < 0 ? "danger" : "success")}
            ${kpi(__("Net Profit After Errors"), money(f.net_profit, currency), f.net_profit < 0 ? "danger" : "success")}
            ${kpi(__("Gross Margin"), `${number(f.gross_margin_percent)}%`, f.gross_margin_percent < 0 ? "danger" : "success")}
            ${kpi(__("Factory Error Cost"), money(f.factory_error_cost, currency), f.factory_error_cost > 0 ? "warning" : "")}
            ${kpi(__("Net Waste Cost"), money(ws.net_waste_cost, currency), ws.net_waste_cost > 0 ? "warning" : "")}
            ${kpi(__("Rework Hours"), number(os.rework_hours))}
            ${kpi(__("Incomplete Costing"), f.incomplete_costing_orders || 0, f.incomplete_costing_orders ? "danger" : "success")}
        </div>
        <div class="reports-grid">
            <section class="reports-wide">${heading(__("Profitability by Factory Order"), __("Revenue uses Sales Order net total before taxes"))}${profitability_table(data.orders || [], currency)}</section>
            <section>${heading(__("Cost Composition"), __("Customer production versus factory-funded errors"))}${cost_breakdown(f, currency)}</section>
            <section>${heading(__("Monthly Profit Trend"), __("Orders grouped by Factory Order date"))}${monthly_table(data.months || [], currency)}</section>
            <section class="reports-wide">${heading(__("Waste and Remnant Recovery by Material"), `${__("Recovered value")}: ${money(ws.recovered_value, currency)} · ${__("Recovery rate")}: ${number(ws.recovery_percent)}%`)}${waste_table(w.materials || [], currency)}</section>
            <section>${heading(__("Stage Productivity"), `${os.completed_operations || 0} ${__("recorded operations")}`)}${stage_table(o.stages || [], currency)}</section>
            <section>${heading(__("Worker Productivity"), `${number(os.work_hours)} ${__("total work hours")}`)}${worker_table(o.workers || [], currency)}</section>
            <section>${heading(__("Workstation Performance"), `${number(os.blocked_hours)} ${__("blocked hours")}`)}${workstation_table(o.workstations || [], currency)}</section>
            <section>${heading(__("Customer Profitability"), __("Sorted by net sales"))}${customer_table(data.customers || [], currency)}</section>
        </div>
    `);
    bind_report_links(page);
}

function profitability_table(rows, currency) {
    const body = rows.slice(0, 50).map(row => `<button class="reports-row reports-order" data-order="${frappe.utils.escape_html(row.name)}">
        <span><b>${frappe.utils.escape_html(row.name)}</b><small>${frappe.utils.escape_html(row.customer || "")}</small></span>
        <span>${money(row.revenue, currency)}<small>${__("Net sales")}</small></span>
        <span>${money(row.total_actual_cost, currency)}<small>${__("Actual cost")}</small></span>
        <span class="${row.net_profit < 0 ? "negative" : "positive"}">${money(row.net_profit, currency)}<small>${number(row.gross_margin_percent)}%</small></span>
        <span class="${row.factory_error_cost > 0 ? "warning-text" : ""}">${money(row.factory_error_cost, currency)}<small>${__("Factory errors")}</small></span>
        <span class="status-${slug(row.costing_status)}">${__(row.costing_status || "Not Started")}</span>
    </button>`).join("");
    return `<div class="reports-table"><div class="reports-row header"><b>${__("Order / Customer")}</b><b>${__("Revenue")}</b><b>${__("Actual Cost")}</b><b>${__("Net Profit")}</b><b>${__("Error Cost")}</b><b>${__("Costing")}</b></div>${body || empty()}</div>`;
}

function cost_breakdown(f, currency) {
    const rows = [
        [__("Customer Materials"), f.customer_material_cost],
        [__("Customer Labor"), f.customer_labor_cost],
        [__("Customer Machines"), f.customer_machine_cost],
        [__("Factory Errors / Rework"), f.factory_error_cost],
        [__("Waste Within Materials"), f.waste_cost],
        [__("Recovered Remnant Value"), -Math.abs(f.remnant_recovery || 0)],
    ];
    const max = Math.max(...rows.map(row => Math.abs(row[1] || 0)), 1);
    return `<div class="report-bars">${rows.map(row => `<div class="report-bar-row"><div><span>${row[0]}</span><b class="${row[1] < 0 ? "positive" : ""}">${money(row[1], currency)}</b></div><div class="report-bar"><i style="width:${Math.min(Math.abs(row[1] || 0) / max * 100, 100)}%"></i></div></div>`).join("")}</div>`;
}

function monthly_table(rows, currency) {
    return `<div class="compact-table"><div class="compact-row header"><b>${__("Month")}</b><b>${__("Orders")}</b><b>${__("Revenue")}</b><b>${__("Profit")}</b><b>${__("Margin")}</b></div>${rows.map(row => `<div class="compact-row"><span>${row.month}</span><span>${row.orders}</span><span>${money(row.revenue, currency)}</span><span class="${row.net_profit < 0 ? "negative" : "positive"}">${money(row.net_profit, currency)}</span><span>${number(row.margin_percent)}%</span></div>`).join("") || empty()}</div>`;
}

function waste_table(rows, currency) {
    return `<div class="reports-table waste-table"><div class="waste-row header"><b>${__("Board Material")}</b><b>${__("Cutting Orders")}</b><b>${__("Boards")}</b><b>${__("Gross Unused")}</b><b>${__("Recovered")}</b><b>${__("Scrap")}</b><b>${__("Net Waste")}</b></div>${rows.map(row => `<div class="waste-row"><span>${frappe.utils.escape_html(row.board_item || "")}</span><span>${row.cutting_orders}</span><span>${number(row.boards)}</span><span>${money(row.gross_unused_cost, currency)}</span><span class="positive">${money(row.recovered_value, currency)}</span><span>${money(row.explicit_scrap_cost, currency)}</span><b class="${row.net_waste_cost > 0 ? "warning-text" : ""}">${money(row.net_waste_cost, currency)}</b></div>`).join("") || empty()}</div>`;
}

function stage_table(rows, currency) { return operation_table(rows, "stage", currency, __("Stage")); }
function worker_table(rows, currency) { return operation_table(rows, "worker", currency, __("Worker")); }
function workstation_table(rows, currency) { return operation_table(rows, "workstation", currency, __("Workstation")); }
function operation_table(rows, key, currency, label) {
    return `<div class="compact-table operation-table"><div class="operation-row header"><b>${label}</b><b>${__("Completed")}</b><b>${__("Hours")}</b><b>${__("Avg Min")}</b><b>${__("Rework Hrs")}</b><b>${__("Cost")}</b></div>${rows.slice(0, 20).map(row => `<div class="operation-row"><span>${frappe.utils.escape_html(row[key] || "")}</span><span>${row.completed}</span><span>${number((row.work_minutes || 0) / 60)}</span><span>${number(row.avg_minutes)}</span><span>${number((row.rework_minutes || 0) / 60)}</span><span>${money((row.labor_cost || 0) + (row.machine_cost || 0), currency)}</span></div>`).join("") || empty()}</div>`;
}

function customer_table(rows, currency) {
    return `<div class="compact-table customer-table"><div class="customer-row header"><b>${__("Customer")}</b><b>${__("Orders")}</b><b>${__("Revenue")}</b><b>${__("Profit")}</b><b>${__("Margin")}</b></div>${rows.slice(0, 20).map(row => `<div class="customer-row"><span>${frappe.utils.escape_html(row.customer)}</span><span>${row.orders}</span><span>${money(row.revenue, currency)}</span><span class="${row.net_profit < 0 ? "negative" : "positive"}">${money(row.net_profit, currency)}</span><span>${number(row.margin_percent)}%</span></div>`).join("") || empty()}</div>`;
}

function bind_report_links(page) {
    page.main.find("[data-order]").on("click", function () { frappe.set_route("Form", "Factory Order", $(this).data("order")); });
}
function heading(title, subtitle) { return `<div class="reports-heading"><h3>${title}</h3><span>${subtitle || ""}</span></div>`; }
function kpi(label, value, tone = "") { return `<div class="reports-kpi ${tone}"><span>${label}</span><b>${value}</b></div>`; }
function money(value, currency) { return frappe.format(Number(value || 0), {fieldtype: "Currency", options: currency}); }
function number(value) { return Number(value || 0).toFixed(2); }
function empty() { return `<div class="reports-empty">${__("No data for the selected filters")}</div>`; }
function slug(value) { return (value || "").toLowerCase().replaceAll(" ", "-"); }
