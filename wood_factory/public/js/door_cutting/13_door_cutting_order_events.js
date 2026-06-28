// =====================================================
// ERPNext Form Events
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    // هذا هو الملف الرئيسي الذي يربط الملفات السابقة مع فورم ERPNext.
    // يجب تحميله أخيرًا بعد كل ملفات الحساب والرسم والتصدير.
    const { EDGE_OPTIONS, PACKING_OPTIONS, setup_pieces_excel_ux, calculate_order, print_cutting_plan, export_cutting_plan_dxf } = DCO;

    // =====================================================
    // Events
    // =====================================================

    frappe.ui.form.on("Door Cutting Order", {
        setup(frm) {
            frm.set_query("board_item", function () {
                return {
                    filters: {
                        custom_is_mdf: 1
                    }
                };
            });

            frm.set_df_property("edge_type", "options", EDGE_OPTIONS.join("\n"));
            frm.set_df_property("packing_mode", "options", PACKING_OPTIONS.join("\n"));
        },

        refresh(frm) {
            frm.set_df_property("edge_type", "options", EDGE_OPTIONS.join("\n"));
            frm.set_df_property("packing_mode", "options", PACKING_OPTIONS.join("\n"));

            if (frm.is_new()) {
                if (!frm.doc.order_date) {
                    frm.set_value("order_date", frappe.datetime.get_today());
                }

                if (!frm.doc.cutting_cost_per_board_usd) {
                    frm.set_value("cutting_cost_per_board_usd", 1);
                }

                if (!frm.doc.kerf_mm) {
                    frm.set_value("kerf_mm", 3);
                }

                if (!frm.doc.trim_margin_mm) {
                    frm.set_value("trim_margin_mm", 5);
                }

                if (!frm.doc.packing_mode) {
                    frm.set_value("packing_mode", "Auto");
                }
            }

            setup_pieces_excel_ux(frm);

            if (!frm._dco_added_button) {
                frm.add_custom_button("إعادة حساب خطة القص", function () {
                    calculate_order(frm);
                });

                frm.add_custom_button("طباعة خطة القص", function () {
                   print_cutting_plan(frm);
                });

                frm.add_custom_button("تصدير DXF", function () {
                    export_cutting_plan_dxf(frm);
                });

                frm._dco_added_button = true;
            }

            calculate_order(frm);
        },

        validate(frm) {
            calculate_order(frm);
        },

        customer(frm) {
            calculate_order(frm);
        },

        board_item(frm) {
            calculate_order(frm);
        },

        board_rate_usd(frm) {
            calculate_order(frm);
        },

        edge_type(frm) {
            calculate_order(frm);
        },

        edge_rate_usd(frm) {
            calculate_order(frm);
        },

        cutting_cost_per_board_usd(frm) {
            calculate_order(frm);
        },

        kerf_mm(frm) {
            calculate_order(frm);
        },

        trim_margin_mm(frm) {
            calculate_order(frm);
        },

        packing_mode(frm) {
            frm.set_value("packing_method", "جاري إعادة الحساب حسب: " + (frm.doc.packing_mode || "Auto"));

            setTimeout(function () {
                calculate_order(frm);
            }, 200);
        },

        pieces_add(frm) {
            calculate_order(frm);
        },

        pieces_remove(frm) {
            calculate_order(frm);
        }
    });

    frappe.ui.form.on("Door Cutting Order Detail", {
        piece_no(frm) {
            calculate_order(frm);
        },

        width_cm(frm) {
            calculate_order(frm);
        },

        length_cm(frm) {
            calculate_order(frm);
        },

        qty(frm) {
            calculate_order(frm);
        },

        edge_long_right(frm) {
            calculate_order(frm);
        },

        edge_long_left(frm) {
            calculate_order(frm);
        },

        edge_width_top(frm) {
            calculate_order(frm);
        },

        edge_width_bottom(frm) {
            calculate_order(frm);
        },

        allow_rotation(frm) {
            calculate_order(frm);
        },

        notes(frm) {
            calculate_order(frm);
        }
    });
})();
