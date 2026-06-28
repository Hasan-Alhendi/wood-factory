// =====================================================
// Evaluate + Choose Best Plan
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { normalize_mode, sort_pieces, pack_maxrects, pack_shelf_horizontal, pack_shelf_vertical, pack_shelf_first_fit, pack_shelf_next_fit, pack_guillotine, pack_skyline } = DCO;

    // =====================================================
    // Evaluate + choose
    // =====================================================

    function evaluate_plan(plan, pieces, board_w_cm, board_h_cm, method_label, method_key, complexity = 1) {
        const used_area = pieces.reduce((sum, p) => sum + p.area_m2, 0);
        const total_board_area = plan.sheets.length * (board_w_cm * board_h_cm / 10000);
        const waste_area = Math.max(0, total_board_area - used_area);

        const score =
            (plan.unplaced.length * 1000000000) +
            (plan.sheets.length * 1000000) +
            (waste_area * 1000) +
            complexity;

        return {
            method_key,
            method_label,
            sheets: plan.sheets,
            unplaced: plan.unplaced,
            used_area_m2: used_area,
            total_board_area_m2: total_board_area,
            waste_area_m2: waste_area,
            score,
            complexity
        };
    }

    function run_single_method(pieces, board_w_cm, board_h_cm, kerf_cm, method_key) {
        method_key = normalize_mode(method_key);

        if (method_key === "MaxRects Best Short Side") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "best_short_side");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - Best Short Side", method_key, 3);
        }

        if (method_key === "MaxRects Best Area") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "best_area");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - Best Area", method_key, 4);
        }

        if (method_key === "MaxRects Bottom Left") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "bottom_left");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - Bottom Left", method_key, 5);
        }

        if (method_key === "MaxRects Contact Point") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "contact_point");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - Contact Point", method_key, 4);
        }

        if (method_key === "MaxRects Width") {
            const sorted = sort_pieces(pieces, "width_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "best_short_side");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - الأعرض أولاً", method_key, 3);
        }

        if (method_key === "MaxRects Length") {
            const sorted = sort_pieces(pieces, "length_desc");
            const plan = pack_maxrects(sorted, board_w_cm, board_h_cm, kerf_cm, "best_short_side");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "MaxRects - الأطول أولاً", method_key, 3);
        }

        if (method_key === "Shelf Horizontal") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_shelf_horizontal(sorted, board_w_cm, board_h_cm, kerf_cm);
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Shelf Packing - صفوف أفقية", method_key, 20);
        }

        if (method_key === "Shelf Vertical") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_shelf_vertical(sorted, board_w_cm, board_h_cm, kerf_cm);
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Shelf Packing - أعمدة عمودية", method_key, 20);
        }

        if (method_key === "Shelf First Fit") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_shelf_first_fit(sorted, board_w_cm, board_h_cm, kerf_cm);
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Shelf Packing - First Fit", method_key, 18);
        }

        if (method_key === "Shelf Next Fit") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_shelf_next_fit(sorted, board_w_cm, board_h_cm, kerf_cm);
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Shelf Packing - Next Fit", method_key, 22);
        }

        if (method_key === "Guillotine Short Axis") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_guillotine(sorted, board_w_cm, board_h_cm, kerf_cm, "short_axis", "best_area");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Guillotine - Short Axis Split", method_key, 10);
        }

        if (method_key === "Guillotine Long Axis") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_guillotine(sorted, board_w_cm, board_h_cm, kerf_cm, "long_axis", "best_area");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Guillotine - Long Axis Split", method_key, 10);
        }

        if (method_key === "Guillotine Best Area Fit") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_guillotine(sorted, board_w_cm, board_h_cm, kerf_cm, "short_axis", "best_area");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Guillotine - Best Area Fit", method_key, 9);
        }

        if (method_key === "Guillotine Best Short Side Fit") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_guillotine(sorted, board_w_cm, board_h_cm, kerf_cm, "short_axis", "best_short_side");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Guillotine - Best Short Side Fit", method_key, 9);
        }

        if (method_key === "Guillotine Best Long Side Fit") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_guillotine(sorted, board_w_cm, board_h_cm, kerf_cm, "long_axis", "best_long_side");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Guillotine - Best Long Side Fit", method_key, 9);
        }

        if (method_key === "Skyline Bottom Left") {
            const sorted = sort_pieces(pieces, "long_side_desc");
            const plan = pack_skyline(sorted, board_w_cm, board_h_cm, kerf_cm, "bottom_left");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Skyline - Bottom Left", method_key, 12);
        }

        if (method_key === "Skyline Best Fit") {
            const sorted = sort_pieces(pieces, "area_desc");
            const plan = pack_skyline(sorted, board_w_cm, board_h_cm, kerf_cm, "best_fit");
            return evaluate_plan(plan, pieces, board_w_cm, board_h_cm, "Skyline - Best Fit", method_key, 12);
        }

        return run_single_method(pieces, board_w_cm, board_h_cm, kerf_cm, "MaxRects Best Short Side");
    }

    function choose_best_plan(pieces, board_w_cm, board_h_cm, kerf_cm, selected_mode) {
        const mode = normalize_mode(selected_mode);

        const methods = [
            "MaxRects Best Short Side",
            "MaxRects Best Area",
            "MaxRects Bottom Left",
            "MaxRects Contact Point",
            "MaxRects Width",
            "MaxRects Length",
            "Shelf Horizontal",
            "Shelf Vertical",
            "Shelf First Fit",
            "Shelf Next Fit",
            "Guillotine Short Axis",
            "Guillotine Long Axis",
            "Guillotine Best Area Fit",
            "Guillotine Best Short Side Fit",
            "Guillotine Best Long Side Fit",
            "Skyline Bottom Left",
            "Skyline Best Fit"
        ];

        if (mode !== "Auto") {
            return run_single_method(pieces, board_w_cm, board_h_cm, kerf_cm, mode);
        }

        let best = null;

        methods.forEach(method => {
            const result = run_single_method(pieces, board_w_cm, board_h_cm, kerf_cm, method);

            if (!best || result.score < best.score) {
                best = result;
            }
        });

        if (best) {
            best.method_label = "Auto اختار: " + best.method_label;
        }

        return best;
    }

    Object.assign(DCO, {
        evaluate_plan,
        run_single_method,
        choose_best_plan
    });
})();
