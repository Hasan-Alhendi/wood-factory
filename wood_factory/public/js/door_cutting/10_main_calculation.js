// =====================================================
// Main Order Calculation
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { num, round, EDGE_RATES, calculate_piece, expand_pieces, choose_best_plan, render_cutting_plan_html } = DCO;

    // =====================================================
    // Main calculation
    // =====================================================

    function clear_plan(frm, edge_cost) {
        frm.set_value("required_boards", 0);
        frm.set_value("mdf_cost_usd", 0);
        frm.set_value("cutting_cost_usd", 0);
        frm.set_value("total_cost_usd", edge_cost || 0);
        frm.set_value("cutting_plan_html", "");
        frm.set_value("waste_area_m2", 0);
        frm.set_value("waste_percent", 0);
        frm.set_value("packing_method", "");
        frm.set_value("packing_score", "");
    }

    function calculate_order(frm) {
        frm._dco_calc_version = (frm._dco_calc_version || 0) + 1;
        const calc_version = frm._dco_calc_version;

        let total_area = 0;
        let total_edge_meters = 0;

        (frm.doc.pieces || []).forEach(row => {
            calculate_piece(row);
            total_area += num(row.area_m2);
            total_edge_meters += num(row.edge_meters);
        });

        total_area = round(total_area, 3);
        total_edge_meters = round(total_edge_meters, 3);

        frm.refresh_field("pieces");

        frm.set_value("total_area_m2", total_area);
        frm.set_value("total_edge_meters", total_edge_meters);

        let edge_rate = num(frm.doc.edge_rate_usd);

        if (frm.doc.edge_type && EDGE_RATES[frm.doc.edge_type] !== undefined) {
            edge_rate = EDGE_RATES[frm.doc.edge_type];
            frm.set_value("edge_rate_usd", edge_rate);
        }

        const edge_cost = round(total_edge_meters * edge_rate, 3);
        frm.set_value("edge_cost_usd", edge_cost);

        if (!frm.doc.board_item) {
            clear_plan(frm, edge_cost);
            return;
        }

        frappe.db.get_value(
            "Item",
            frm.doc.board_item,
            ["custom_board_length_mm", "custom_board_width_mm"]
        ).then(r => {
            if (calc_version !== frm._dco_calc_version) return;

            const data = r.message || {};

            const full_board_length_cm = num(data.custom_board_length_mm) / 10;
            const full_board_width_cm = num(data.custom_board_width_mm) / 10;

            if (!full_board_length_cm || !full_board_width_cm) {
                clear_plan(frm, edge_cost);
                frappe.show_alert({
                    message: "أبعاد اللوح غير موجودة في صنف MDF.",
                    indicator: "orange"
                });
                return;
            }

            const trim_cm = (num(frm.doc.trim_margin_mm) || 5) / 10;
            const kerf_cm = (num(frm.doc.kerf_mm) || 3) / 10;

            const usable_board_length_cm = full_board_length_cm - (trim_cm * 2);
            const usable_board_width_cm = full_board_width_cm - (trim_cm * 2);

            const expanded = expand_pieces(frm.doc.pieces || []);

            const plan = choose_best_plan(
                expanded,
                usable_board_length_cm,
                usable_board_width_cm,
                kerf_cm,
                frm.doc.packing_mode || "Auto"
            );

            if (!plan) {
                clear_plan(frm, edge_cost);
                return;
            }

            const required_boards = plan.sheets.length;
            const board_rate = num(frm.doc.board_rate_usd);
            const cutting_cost_per_board = num(frm.doc.cutting_cost_per_board_usd) || 1;

            const mdf_cost = round(required_boards * board_rate, 3);
            const cutting_cost = round(required_boards * cutting_cost_per_board, 3);
            const total_cost = round(mdf_cost + edge_cost + cutting_cost, 3);

            const waste_area = round(plan.waste_area_m2, 3);

            let waste_percent = 0;
            if (plan.total_board_area_m2 > 0) {
                waste_percent = round((waste_area / plan.total_board_area_m2) * 100, 2);
            }

            const html = render_cutting_plan_html(
                plan,
                usable_board_length_cm,
                usable_board_width_cm,
                full_board_length_cm,
                full_board_width_cm,
                kerf_cm,
                trim_cm,
                frm
            );

            const score_text =
                "ألواح: " + required_boards +
                " | هدر: " + waste_percent + "%" +
                " | غير مدخل: " + (plan.unplaced ? plan.unplaced.length : 0) +
                " | الخوارزمية: " + plan.method_label;

            frm.set_value("required_boards", required_boards);
            frm.set_value("mdf_cost_usd", mdf_cost);
            frm.set_value("cutting_cost_usd", cutting_cost);
            frm.set_value("total_cost_usd", total_cost);

            frm.set_value("waste_area_m2", waste_area);
            frm.set_value("waste_percent", waste_percent);
            frm.set_value("packing_method", plan.method_label);
            frm.set_value("packing_score", score_text);
            frm.set_value("cutting_plan_html", html);

            frm.refresh_field("required_boards");
            frm.refresh_field("waste_area_m2");
            frm.refresh_field("waste_percent");
            frm.refresh_field("packing_method");
            frm.refresh_field("packing_score");
            frm.refresh_field("cutting_plan_html");
        });
    }

    Object.assign(DCO, {
        clear_plan,
        calculate_order
    });
})();
