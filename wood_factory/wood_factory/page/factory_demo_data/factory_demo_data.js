frappe.pages["factory-demo-data"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Factory Demo Data"),
        single_column: true,
    });
    page.main.addClass("factory-demo-data-page");
    page.company_field = page.add_field({
        fieldname: "company",
        label: __("Company"),
        fieldtype: "Link",
        options: "Company",
        reqd: 1,
        default: frappe.defaults.get_user_default("Company"),
        change: () => load_demo_status(page),
    });
    page.users_field = page.add_field({
        fieldname: "include_users",
        label: __("Create Disabled Demo Users"),
        fieldtype: "Check",
        default: 1,
    });
    page.stock_field = page.add_field({
        fieldname: "include_stock",
        label: __("Create Demo Stock Receipt"),
        fieldtype: "Check",
        default: 1,
    });
    page.set_primary_action(__("Generate Demo Dataset"), () => generate_demo_data(page));
    page.add_inner_button(__("Refresh Status"), () => load_demo_status(page));
    page.add_inner_button(__("Control Center"), () => frappe.set_route("factory-control-center"));
    load_demo_status(page);
};

function load_demo_status(page) {
    frappe.call({
        method: "wood_factory.demo_dataset.get_demo_status",
        args: {company: page.company_field.get_value()},
    }).then(r => render_demo_status(page, r.message || {}));
}

function generate_demo_data(page) {
    const company = page.company_field.get_value();
    if (!company) {
        frappe.msgprint(__("Select a company first"));
        return;
    }
    const includeStock = page.stock_field.get_value();
    const stockWarning = includeStock
        ? `<br><br><b>${__("A submitted Material Receipt will be created once for the demo warehouses.")}</b>`
        : "";
    frappe.confirm(
        `${__("Create or refresh the Wood Factory demo dataset for {0}?", [company])}${stockWarning}<br><br>${__("The operation is idempotent and does not delete production data.")}`,
        () => {
            frappe.call({
                method: "wood_factory.demo_dataset.create_demo_dataset",
                args: {
                    company,
                    include_users: page.users_field.get_value(),
                    include_stock: includeStock,
                },
                freeze: true,
                freeze_message: __("Generating realistic factory demo data..."),
            }).then(r => {
                const data = r.message || {};
                render_demo_status(page, data);
                const warnings = data.warnings || [];
                if (warnings.length) {
                    frappe.msgprint({
                        title: __("Demo Dataset Created with Warnings"),
                        indicator: "orange",
                        message: `<ul>${warnings.map(x => `<li>${frappe.utils.escape_html(x)}</li>`).join("")}</ul>`,
                    });
                } else {
                    frappe.show_alert({message: __("Factory demo dataset is ready"), indicator: "green"});
                }
            });
        }
    );
}

function render_demo_status(page, data) {
    const counts = data.counts || {};
    const scenarios = data.scenarios || [];
    const warnings = data.warnings || [];
    page.main.html(`
        <div class="demo-safety">
            <div>
                <b>${__("Safe Demonstration Dataset")}</b>
                <span>${__("Uses a company-specific prefix, disabled example users, and idempotent creation. It never deletes production records.")}</span>
            </div>
            <strong class="demo-ready ${data.ready ? "yes" : "no"}">${data.ready ? __("Ready") : __("Not Generated")}</strong>
        </div>
        <div class="demo-kpis">
            ${demo_kpi(__("Items"), counts.items)}
            ${demo_kpi(__("Customers"), counts.customers)}
            ${demo_kpi(__("Workstations"), counts.workstations)}
            ${demo_kpi(__("Disabled Users"), counts.users)}
            ${demo_kpi(__("Factory Orders"), counts.factory_orders)}
            ${demo_kpi(__("Exceptions"), counts.piece_exceptions, "warning")}
            ${demo_kpi(__("Remnants"), counts.remnants)}
            ${demo_kpi(__("Alerts"), counts.alerts, "warning")}
        </div>
        <section class="demo-section">
            <div class="demo-section-head">
                <div><h3>${__("Realistic Scenarios")}</h3><span>${frappe.utils.escape_html(data.company || "")}</span></div>
                <code>${frappe.utils.escape_html(data.prefix || "")}</code>
            </div>
            <div class="demo-table">
                <div class="demo-row header"><b>${__("Scenario")}</b><b>${__("Purpose")}</b><b>${__("Factory Order")}</b><b>${__("Status")}</b></div>
                ${scenarios.map(row => `
                    <button class="demo-row ${row.factory_order ? "available" : "missing"}" ${row.factory_order ? `data-order="${row.factory_order}"` : "disabled"}>
                        <b>${frappe.utils.escape_html(row.code)}</b>
                        <span>${frappe.utils.escape_html(row.description || "")}</span>
                        <span>${frappe.utils.escape_html(row.factory_order || "-")}</span>
                        <strong>${__(row.status || "Missing")}</strong>
                    </button>
                `).join("")}
            </div>
        </section>
        ${warnings.length ? `<section class="demo-section demo-warning"><h3>${__("Warnings")}</h3><ul>${warnings.map(x => `<li>${frappe.utils.escape_html(x)}</li>`).join("")}</ul></section>` : ""}
        <section class="demo-section demo-notes">
            <h3>${__("Safety Notes")}</h3>
            <ul>${(data.notes || []).map(x => `<li>${frappe.utils.escape_html(x)}</li>`).join("")}</ul>
        </section>
    `);
    page.main.find("[data-order]").on("click", function () {
        frappe.set_route("Form", "Factory Order", $(this).data("order"));
    });
}

function demo_kpi(label, value, tone = "") {
    return `<div class="demo-kpi ${tone}"><span>${label}</span><b>${value || 0}</b></div>`;
}
