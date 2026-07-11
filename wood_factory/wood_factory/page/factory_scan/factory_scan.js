frappe.pages["factory-scan"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("Factory Scan"), single_column: true});
    page.main.addClass("factory-scan-page");
    page.main.html(`<div class="scan-panel"><h2>${__("Scan Factory Code")}</h2><p class="text-muted">${__("Scan the whole order code. Only exception pieces are opened separately.")}</p><input class="form-control scan-input" type="text" autocomplete="off" placeholder="WF:FO:... / WF:FP:..."><button class="btn btn-primary scan-submit">${__("Open Work")}</button></div><div class="scan-result"></div>`);
    const input = page.main.find(".scan-input");
    page.main.find(".scan-submit").on("click", () => resolve_scan(page));
    input.on("keydown", event => { if (event.key === "Enter") resolve_scan(page); });
    setTimeout(() => input.trigger("focus"), 100);
};

function resolve_scan(page) {
    const input = page.main.find(".scan-input"), code = input.val().trim();
    if (!code) return;
    frappe.call({method: "wood_factory.wood_factory.page.factory_scan.factory_scan.resolve_scan", args: {code}, freeze: true}).then(r => {
        const result = r.message || {};
        render_scan_result(page, result);
        input.val("").trigger("focus");
    });
}

function render_scan_result(page, result) {
    const box = page.main.find(".scan-result");
    const title = result.kind === "order" ? result.name : (result.part_name || result.piece_uid);
    const detail = result.kind === "order" ? `${result.customer || ""} · ${result.progress_percent || 0}%` : `${result.factory_order} · ${result.width_mm} × ${result.height_mm} mm`;
    box.html(`<div class="scan-card ${result.kind === "piece" ? "scan-exception" : ""}"><div><h3>${frappe.utils.escape_html(title || "")}</h3><div>${frappe.utils.escape_html(detail)}</div><strong>${__(result.stage || "")} · ${__(result.status || "")}</strong>${result.message ? `<p>${__(result.message)}</p>` : ""}</div><button class="btn btn-primary scan-open">${__("Open Work")}</button></div>`);
    box.find(".scan-open").on("click", () => frappe.set_route(...result.route));
}
