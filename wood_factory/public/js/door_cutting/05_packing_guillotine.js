// =====================================================
// Guillotine Packing
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { orientations_for, make_placed_piece, prune_free_rects, create_sheet } = DCO;

    // =====================================================
    // Guillotine Packing
    // =====================================================

    function find_best_position_guillotine(sheet, piece, fit_mode) {
        let best = null;

        sheet.free_rects.forEach((free, free_index) => {
            orientations_for(piece).forEach(o => {
                if (o.w <= free.w && o.h <= free.h) {
                    const leftover_area = (free.w * free.h) - (o.w * o.h);
                    const short_side = Math.min(free.w - o.w, free.h - o.h);
                    const long_side = Math.max(free.w - o.w, free.h - o.h);

                    let score = leftover_area * 1000 + short_side;

                    if (fit_mode === "best_area") score = leftover_area * 100000 + short_side;
                    if (fit_mode === "best_short_side") score = short_side * 100000 + leftover_area;
                    if (fit_mode === "best_long_side") score = long_side * 100000 + leftover_area;

                    if (!best || score < best.score) {
                        best = {
                            x: free.x,
                            y: free.y,
                            w: o.w,
                            h: o.h,
                            rotated: o.rotated,
                            free_index,
                            score
                        };
                    }
                }
            });
        });

        return best;
    }

    function place_piece_guillotine(sheet, piece, position, kerf_cm, split_mode) {
        sheet.pieces.push(make_placed_piece(
            piece,
            position.x,
            position.y,
            position.w,
            position.h,
            position.rotated
        ));

        const free = sheet.free_rects[position.free_index];
        sheet.free_rects.splice(position.free_index, 1);

        const remaining_w = free.w - position.w - kerf_cm;
        const remaining_h = free.h - position.h - kerf_cm;
        const min_size = 0.01;

        const right_full = {
            x: free.x + position.w + kerf_cm,
            y: free.y,
            w: remaining_w,
            h: free.h
        };

        const bottom_trimmed = {
            x: free.x,
            y: free.y + position.h + kerf_cm,
            w: position.w,
            h: remaining_h
        };

        const right_trimmed = {
            x: free.x + position.w + kerf_cm,
            y: free.y,
            w: remaining_w,
            h: position.h
        };

        const bottom_full = {
            x: free.x,
            y: free.y + position.h + kerf_cm,
            w: free.w,
            h: remaining_h
        };

        function add(r) {
            if (r.w > min_size && r.h > min_size) sheet.free_rects.push(r);
        }

        if (split_mode === "long_axis") {
            if (remaining_w > remaining_h) {
                add(right_full);
                add(bottom_trimmed);
            } else {
                add(right_trimmed);
                add(bottom_full);
            }
        } else {
            if (remaining_w < remaining_h) {
                add(right_full);
                add(bottom_trimmed);
            } else {
                add(right_trimmed);
                add(bottom_full);
            }
        }

        sheet.free_rects = prune_free_rects(sheet.free_rects);
    }

    function pack_guillotine(pieces, board_w_cm, board_h_cm, kerf_cm, split_mode, fit_mode) {
        const sheets = [];
        const unplaced = [];

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                const pos = find_best_position_guillotine(sheet, piece, fit_mode);

                if (pos) {
                    place_piece_guillotine(sheet, piece, pos, kerf_cm, split_mode);
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = create_sheet(sheets.length + 1, board_w_cm, board_h_cm);
                const pos = find_best_position_guillotine(sheet, piece, fit_mode);

                if (pos) {
                    place_piece_guillotine(sheet, piece, pos, kerf_cm, split_mode);
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        return { sheets, unplaced };
    }

    Object.assign(DCO, {
        find_best_position_guillotine,
        place_piece_guillotine,
        pack_guillotine
    });
})();
