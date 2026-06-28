// =====================================================
// DXF Export
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { num, round, expand_pieces, choose_best_plan } = DCO;

    function dxf_escape_text(value) {
        return String(value || "")
            .replace(/[^\x20-\x7E]/g, "")
            .replace(/\\/g, "/")
            .trim();
    }

    function dxf_line(layer, x1, y1, x2, y2) {
        return [
            "0", "LINE",
            "8", layer,
            "10", round(x1, 3),
            "20", round(y1, 3),
            "30", 0,
            "11", round(x2, 3),
            "21", round(y2, 3),
            "31", 0
        ].join("\n") + "\n";
    }

    function dxf_text(layer, x, y, height, text) {
        return [
            "0", "TEXT",
            "8", layer,
            "10", round(x, 3),
            "20", round(y, 3),
            "30", 0,
            "40", height,
            "1", dxf_escape_text(text),
            "50", 0
        ].join("\n") + "\n";
    }

    function dxf_rect(layer, x, y, w, h) {
        let dxf = "";

        dxf += dxf_line(layer, x, y, x + w, y);
        dxf += dxf_line(layer, x + w, y, x + w, y + h);
        dxf += dxf_line(layer, x + w, y + h, x, y + h);
        dxf += dxf_line(layer, x, y + h, x, y);

        return dxf;
    }

    function make_dxf_document(entities) {
        return [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1009",
            "9", "$INSUNITS",
            "70", "4",
            "0", "ENDSEC",

            "0", "SECTION",
            "2", "TABLES",

            "0", "TABLE",
            "2", "LAYER",
            "70", "4",

            "0", "LAYER",
            "2", "SHEET_OUTLINE",
            "70", "0",
            "62", "8",
            "6", "CONTINUOUS",

            "0", "LAYER",
            "2", "CUT_PATH",
            "70", "0",
            "62", "1",
            "6", "CONTINUOUS",

            "0", "LAYER",
            "2", "LABEL",
            "70", "0",
            "62", "3",
            "6", "CONTINUOUS",

            "0", "LAYER",
            "2", "INFO",
            "70", "0",
            "62", "5",
            "6", "CONTINUOUS",

            "0", "ENDTAB",
            "0", "ENDSEC",

            "0", "SECTION",
            "2", "ENTITIES",
            entities,
            "0", "ENDSEC",
            "0", "EOF"
        ].join("\n");
    }

    function download_text_file(filename, content, mime_type) {
        const blob = new Blob([content], {
            type: mime_type || "application/dxf"
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");

        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        setTimeout(function () {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 500);
    }

    function export_cutting_plan_dxf(frm) {
        if (!frm.doc.board_item) {
            frappe.msgprint("اختر نوع اللوح أولًا.");
            return;
        }

        frappe.db.get_value(
            "Item",
            frm.doc.board_item,
            ["custom_board_length_mm", "custom_board_width_mm"]
        ).then(r => {
            const data = r.message || {};

            const full_board_length_mm = num(data.custom_board_length_mm);
            const full_board_width_mm = num(data.custom_board_width_mm);

            if (!full_board_length_mm || !full_board_width_mm) {
                frappe.msgprint("أبعاد اللوح غير موجودة داخل صنف MDF.");
                return;
            }

            const full_board_length_cm = full_board_length_mm / 10;
            const full_board_width_cm = full_board_width_mm / 10;

            const trim_mm = num(frm.doc.trim_margin_mm) || 5;
            const kerf_mm = num(frm.doc.kerf_mm) || 3;

            const trim_cm = trim_mm / 10;
            const kerf_cm = kerf_mm / 10;

            const usable_board_length_cm = full_board_length_cm - (trim_cm * 2);
            const usable_board_width_cm = full_board_width_cm - (trim_cm * 2);

            const expanded = expand_pieces(frm.doc.pieces || []);

            if (!expanded.length) {
                frappe.msgprint("لا توجد درف لتصديرها.");
                return;
            }

            const plan = choose_best_plan(
                expanded,
                usable_board_length_cm,
                usable_board_width_cm,
                kerf_cm,
                frm.doc.packing_mode || "Auto"
            );

            if (!plan || !plan.sheets || !plan.sheets.length) {
                frappe.msgprint("لم يتم توليد خطة قص صالحة للتصدير.");
                return;
            }

            const sheet_gap_mm = 300;
            let entities = "";

            entities += dxf_text(
                "INFO",
                0,
                full_board_width_mm + 120,
                35,
                "ERPNext Cutting Plan - " + (frm.doc.name || "")
            );

            entities += dxf_text(
                "INFO",
                0,
                full_board_width_mm + 75,
                25,
                "Board: " + dxf_escape_text(frm.doc.board_item || "")
            );

            entities += dxf_text(
                "INFO",
                0,
                full_board_width_mm + 40,
                25,
                "Algorithm: " + dxf_escape_text(plan.method_label || "")
            );

            plan.sheets.forEach(sheet => {
                const sheet_offset_x = (sheet.sheet_no - 1) * (full_board_length_mm + sheet_gap_mm);
                const sheet_offset_y = 0;

                // حدود اللوح الكامل
                entities += dxf_rect(
                    "SHEET_OUTLINE",
                    sheet_offset_x,
                    sheet_offset_y,
                    full_board_length_mm,
                    full_board_width_mm
                );

                entities += dxf_text(
                    "LABEL",
                    sheet_offset_x + 20,
                    sheet_offset_y + full_board_width_mm + 25,
                    22,
                    "Sheet " + sheet.sheet_no
                );

                sheet.pieces.forEach(p => {
                    const piece_w_mm = p.w * 10;
                    const piece_h_mm = p.h * 10;

                    /*
                        p.x و p.y في الخطة محسوبة من أعلى اللوح المفيد.
                        DXF عادةً يستخدم نقطة الأصل أسفل يسار.
                        لذلك نحول Y ليظهر بنفس شكل الخطة داخل اللوح.
                    */
                    const x_mm = sheet_offset_x + trim_mm + (p.x * 10);

                    const y_mm =
                        sheet_offset_y +
                        full_board_width_mm -
                        trim_mm -
                        (p.y * 10) -
                        piece_h_mm;

                    // مسار القص
                    entities += dxf_rect(
                        "CUT_PATH",
                        x_mm,
                        y_mm,
                        piece_w_mm,
                        piece_h_mm
                    );

                    // رقم القطعة داخل المستطيل
                    entities += dxf_text(
                        "LABEL",
                        x_mm + 8,
                        y_mm + Math.max(8, piece_h_mm / 2),
                        18,
                        String(p.label || "")
                    );

                    // المقاس
                    entities += dxf_text(
                        "LABEL",
                        x_mm + 8,
                        y_mm + Math.max(28, piece_h_mm / 2 - 22),
                        14,
                        round(p.original_w, 1) + "x" + round(p.original_h, 1) + "cm"
                    );
                });
            });

            const dxf = make_dxf_document(entities);

            const filename =
                "cutting_plan_" +
                String(frm.doc.name || "door_cutting_order").replace(/[^\w\-]+/g, "_") +
                ".dxf";

            download_text_file(filename, dxf, "application/dxf");

            frappe.show_alert({
                message: "تم تصدير ملف DXF بنجاح.",
                indicator: "green"
            });
        });
    }

    Object.assign(DCO, {
        dxf_escape_text,
        dxf_line,
        dxf_text,
        dxf_rect,
        make_dxf_document,
        download_text_file,
        export_cutting_plan_dxf
    });
})();
