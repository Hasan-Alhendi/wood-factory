// =====================================================
// Excel-like UX for Pieces Grid
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { calculate_order } = DCO;

    // =====================================================
    // Excel-like UX for Pieces Grid
    // يجعل جدول الدرف أعرض + Enter يضيف سطر جديد
    // =====================================================

    function setup_pieces_excel_ux(frm) {
        if (!frm.fields_dict.pieces || !frm.fields_dict.pieces.grid) {
            return;
        }

        const grid = frm.fields_dict.pieces.grid;
        const $grid_wrapper = $(grid.wrapper);

        // إضافة CSS مرة واحدة فقط
        if (!document.getElementById("dco-pieces-excel-ux-css")) {
            $("head").append(`
                <style id="dco-pieces-excel-ux-css">
                    /* توسيع صفحة الطلب */
                    .dco-wide-form .layout-main-section,
                    .dco-wide-form .layout-main-section-wrapper,
                    .dco-wide-form .form-page,
                    .dco-wide-form .form-layout {
                        max-width: none !important;
                        width: 100% !important;
                    }

                    /* جعل جدول الدرف بعرض أكبر */
                    .dco-pieces-wide-control {
                        width: 100% !important;
                        max-width: none !important;
                        flex: 0 0 100% !important;
                        grid-column: 1 / -1 !important;
                    }

                    .dco-pieces-wide-control .grid-body {
                        overflow-x: auto !important;
                    }

                    .dco-pieces-wide-control .grid-row {
                        min-width: 1250px !important;
                    }

                    .dco-pieces-wide-control .grid-heading-row {
                        min-width: 1250px !important;
                    }

                    .dco-pieces-wide-control .grid-static-col,
                    .dco-pieces-wide-control .grid-input {
                        font-size: 14px !important;
                    }

                    .dco-pieces-wide-control .grid-row td,
                    .dco-pieces-wide-control .grid-static-col {
                        padding-top: 8px !important;
                        padding-bottom: 8px !important;
                    }
                </style>
            `);
        }

        // إضافة كلاس للفورم والجدول
        $(frm.wrapper).addClass("dco-wide-form");
        $grid_wrapper.closest(".frappe-control").addClass("dco-pieces-wide-control");

        // منع تكرار ربط الحدث
        $grid_wrapper.off("keydown.dco_enter_add_row");

        // Enter داخل الجدول
        $grid_wrapper.on("keydown.dco_enter_add_row", "input, textarea, select", function (e) {
            if (e.key !== "Enter") {
                return;
            }

            // Shift + Enter داخل الملاحظات يتركه كسطر جديد
            if ($(e.target).is("textarea") && e.shiftKey) {
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            // حفظ القيمة الحالية
            $(e.target).trigger("change");

            const $current_row = $(e.target).closest(".grid-row");

            const $rows = $grid_wrapper
                .find(".grid-row:visible")
                .filter(function () {
                    return $(this).find("[data-fieldname]").length > 0;
                });

            const current_index = $rows.index($current_row);
            const is_last_row = current_index === $rows.length - 1;

            const current_fieldname =
                $(e.target).closest("[data-fieldname]").attr("data-fieldname") || "width_cm";

            // إذا لسنا في آخر سطر، انتقل للسطر التالي في نفس العمود
            if (!is_last_row && current_index >= 0) {
                focus_grid_cell($rows.eq(current_index + 1), current_fieldname);
                return;
            }

            // إذا نحن في آخر سطر، أضف سطر جديد
            grid.add_new_row();

            frm.refresh_field("pieces");

            setTimeout(function () {
                const $new_rows = $grid_wrapper
                    .find(".grid-row:visible")
                    .filter(function () {
                        return $(this).find("[data-fieldname]").length > 0;
                    });

                const $last_row = $new_rows.last();

                // الأفضل أن يبدأ الإدخال من الرقم أو العرض
                focus_grid_cell($last_row, "piece_no");

                // أعد الحساب إذا عندك دالة calculate_order
                if (typeof calculate_order === "function") {
                    calculate_order(frm);
                }
            }, 250);
        });
    }

    function focus_grid_cell($row, fieldname) {
        if (!$row || !$row.length) {
            return;
        }

        let $cell = $row.find(`[data-fieldname="${fieldname}"]`).first();

        if (!$cell.length) {
            $cell = $row.find(`[data-fieldname="width_cm"]`).first();
        }

        if (!$cell.length) {
            $cell = $row.find("[data-fieldname]").first();
        }

        if ($cell.length) {
            $cell.click();

            setTimeout(function () {
                const $input = $row.find("input:visible, textarea:visible, select:visible").first();

                if ($input.length) {
                    $input.focus();

                    if ($input.is("input")) {
                        $input.select();
                    }
                }
            }, 120);
        }
    }

    Object.assign(DCO, {
        setup_pieces_excel_ux,
        focus_grid_cell
    });
})();
