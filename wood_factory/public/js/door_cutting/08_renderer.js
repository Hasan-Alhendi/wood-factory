// =====================================================
// Render Cutting Plan HTML
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { num, round, escape_html } = DCO;

    // =====================================================
    // Rendering
    // =====================================================


    function render_cutting_plan_html(
        plan,
        board_w_cm,
        board_h_cm,
        full_board_w_cm,
        full_board_h_cm,
        kerf_cm,
        trim_cm,
        frm
    ) {
        // يرسم خطة القص داخل حقل HTML في ERPNext.
        // الإحداثيات محفوظة بالسنتيمتر، والرسم يتم كنسبة مئوية حتى يناسب الشاشة والطباعة.
        if (!plan || !plan.sheets || !plan.sheets.length) {
            return "";
        }

        const board_area_m2 = (board_w_cm * board_h_cm) / 10000;
        const used_area_m2 = round(plan.used_area_m2 || 0, 3);
        const total_board_area_m2 = round(plan.total_board_area_m2 || 0, 3);
        const waste_area_m2 = round(plan.waste_area_m2 || 0, 3);
        const waste_percent = total_board_area_m2
            ? round((waste_area_m2 / total_board_area_m2) * 100, 2)
            : 0;

        const board_width_px = 980;
        const board_height_px = Math.max(120, Math.round(board_width_px * (board_h_cm / board_w_cm)));

        let html = `
            <div class="dco-cutting-plan" style="font-family:Arial,Tahoma,sans-serif; direction:rtl; color:#111; background:#fff;">
                <h2 style="margin:0 0 8px 0; font-size:18px;">خطة القص</h2>

                <div style="line-height:1.7; margin-bottom:8px; font-size:12px;">
                    <b>الطلب:</b> ${escape_html(frm.doc.name || "")} &nbsp; | &nbsp;
                    <b>الزبون:</b> ${escape_html(frm.doc.customer || "")} &nbsp; | &nbsp;
                    <b>اللوح:</b> <span dir="ltr">${escape_html(frm.doc.board_item || "")}</span><br>
                    <b>مقاس اللوح الكامل:</b> ${round(full_board_w_cm, 1)} × ${round(full_board_h_cm, 1)} سم &nbsp; | &nbsp;
                    <b>المقاس المستخدم بعد التشذيب:</b> ${round(board_w_cm, 1)} × ${round(board_h_cm, 1)} سم &nbsp; | &nbsp;
                    <b>سماكة القص:</b> ${round(kerf_cm * 10, 1)} مم &nbsp; | &nbsp;
                    <b>هامش التشذيب:</b> ${round(trim_cm * 10, 1)} مم
                </div>

                <div class="dco-summary-grid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:8px 0 12px 0;">
                    <div class="dco-summary-card" style="border:1px solid #ddd; border-radius:8px; padding:8px; background:#f8fafc;">
                        <b>عدد الألواح</b>
                        <span>${plan.sheets.length}</span>
                    </div>
                    <div class="dco-summary-card" style="border:1px solid #ddd; border-radius:8px; padding:8px; background:#f8fafc;">
                        <b>مساحة القطع</b>
                        <span>${used_area_m2} م²</span>
                    </div>
                    <div class="dco-summary-card" style="border:1px solid #ddd; border-radius:8px; padding:8px; background:#f8fafc;">
                        <b>مساحة الهدر</b>
                        <span>${waste_area_m2} م²</span>
                    </div>
                    <div class="dco-summary-card" style="border:1px solid #ddd; border-radius:8px; padding:8px; background:#f8fafc;">
                        <b>نسبة الهدر</b>
                        <span>${waste_percent}%</span>
                    </div>
                </div>

                <div style="font-size:12px; margin-bottom:8px;">
                    <b>طريقة الترتيب:</b> ${escape_html(plan.method_label || "")}
                </div>
        `;

        plan.sheets.forEach(sheet => {
            const sheet_used_area_m2 = round(
                sheet.pieces.reduce((sum, p) => sum + num(p.area_m2), 0),
                3
            );
            const sheet_waste_area_m2 = round(Math.max(0, board_area_m2 - sheet_used_area_m2), 3);
            const sheet_waste_percent = board_area_m2
                ? round((sheet_waste_area_m2 / board_area_m2) * 100, 2)
                : 0;

            html += `
                <div class="dco-sheet-card" style="border:1px solid #bbb; border-radius:10px; padding:10px; margin:14px 0; background:#fff; page-break-inside:avoid; break-inside:avoid;">
                    <div class="dco-sheet-title" style="display:flex; justify-content:space-between; gap:10px; margin-bottom:8px; font-size:13px; font-weight:bold;">
                        <div>اللوح ${sheet.sheet_no}</div>
                        <div>
                            عدد القطع: ${sheet.pieces.length} &nbsp; | &nbsp;
                            الهدر: ${sheet_waste_area_m2} م² (${sheet_waste_percent}%)
                        </div>
                    </div>

                    <div class="dco-sheet-board" style="position:relative; direction:ltr; width:${board_width_px}px; height:${board_height_px}px; max-width:100%; border:2px solid #111; background:linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px), linear-gradient(rgba(0,0,0,0.05) 1px, transparent 1px), #fff; background-size:32px 32px; overflow:hidden; margin:0 auto 8px auto;">
            `;

            sheet.pieces.forEach(p => {
                const left = (p.x / board_w_cm) * 100;
                const top = (p.y / board_h_cm) * 100;
                const width = (p.w / board_w_cm) * 100;
                const height = (p.h / board_h_cm) * 100;

                html += `
                    <div class="dco-piece" style="position:absolute; left:${left}%; top:${top}%; width:${width}%; height:${height}%; border:1px solid #111; background:#e4f5ff; color:#111; overflow:hidden; padding:2px; font-size:10px; line-height:1.2; text-align:center; box-sizing:border-box;">
                        <b>${escape_html(p.label)}</b><br>
                        <span>${round(p.original_w, 1)}×${round(p.original_h, 1)} سم</span><br>
                        <small>${p.rotated ? "مدوّرة" : "بدون تدوير"}</small>
                    </div>
                `;
            });

            html += `
                    </div>

                    <table class="dco-table" style="width:100%; border-collapse:collapse; font-size:11px; margin-top:8px;">
                        <thead>
                            <tr>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">القطعة</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">المقاس الأصلي</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">المقاس على اللوح</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">X</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">Y</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">تدوير</th>
                                <th style="border:1px solid #999; padding:4px; background:#f1f1f1;">ملاحظات</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            sheet.pieces.forEach(p => {
                html += `
                    <tr>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${escape_html(p.label)}</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${round(p.original_w, 1)} × ${round(p.original_h, 1)} سم</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${round(p.w, 1)} × ${round(p.h, 1)} سم</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${round(p.x, 1)}</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${round(p.y, 1)}</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${p.rotated ? "نعم" : "لا"}</td>
                        <td style="border:1px solid #999; padding:4px; text-align:center;">${escape_html(p.notes || "")}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
        });

        if (plan.unplaced && plan.unplaced.length) {
            html += `
                <div style="border:1px solid #d9534f; background:#fff5f5; color:#a94442; padding:8px; border-radius:8px; margin-top:12px;">
                    <b>تنبيه:</b> توجد ${plan.unplaced.length} قطعة لم تدخل ضمن الألواح. راجع المقاسات أو مقاس اللوح أو سماحية التدوير.
                </div>
            `;
        }

        html += `</div>`;
        return html;
    }

    Object.assign(DCO, {
        render_cutting_plan_html
    });
})();
