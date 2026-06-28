// =====================================================
// MaxRects Packing
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { round, orientations_for, make_placed_piece, split_free_rect, prune_free_rects, create_sheet } = DCO;

    // =====================================================
    // MaxRects
    // =====================================================

    function contact_point_score(sheet, x, y, w, h) {
        let score = 0;

        if (x === 0 || round(x + w, 3) === round(sheet.w, 3)) score += h;
        if (y === 0 || round(y + h, 3) === round(sheet.h, 3)) score += w;

        sheet.pieces.forEach(p => {
            if (round(p.x + p.w, 3) === round(x, 3) || round(x + w, 3) === round(p.x, 3)) {
                const overlap = Math.max(0, Math.min(y + h, p.y + p.h) - Math.max(y, p.y));
                score += overlap;
            }

            if (round(p.y + p.h, 3) === round(y, 3) || round(y + h, 3) === round(p.y, 3)) {
                const overlap = Math.max(0, Math.min(x + w, p.x + p.w) - Math.max(x, p.x));
                score += overlap;
            }
        });

        return score;
    }

    function maxrects_score(sheet, free, o, heuristic) {
        const leftover_area = (free.w * free.h) - (o.w * o.h);
        const short_side = Math.min(free.w - o.w, free.h - o.h);
        const long_side = Math.max(free.w - o.w, free.h - o.h);

        if (heuristic === "best_area") {
            return leftover_area * 100000 + short_side * 100 + long_side;
        }

        if (heuristic === "bottom_left") {
            return free.y * 100000 + free.x;
        }

        if (heuristic === "contact_point") {
            const contact = contact_point_score(sheet, free.x, free.y, o.w, o.h);
            return -contact * 100000 + leftover_area;
        }

        return short_side * 100000 + long_side * 100 + leftover_area;
    }

    function find_best_position_maxrects(sheet, piece, heuristic) {
        let best = null;

        sheet.free_rects.forEach((free, free_index) => {
            orientations_for(piece).forEach(o => {
                if (o.w <= free.w && o.h <= free.h) {
                    const score = maxrects_score(sheet, free, o, heuristic);

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

    function place_piece_maxrects(sheet, piece, position, kerf_cm) {
        sheet.pieces.push(make_placed_piece(
            piece,
            position.x,
            position.y,
            position.w,
            position.h,
            position.rotated
        ));

        const used = {
            x: position.x,
            y: position.y,
            w: position.w + kerf_cm,
            h: position.h + kerf_cm
        };

        let new_free_rects = [];

        sheet.free_rects.forEach(free => {
            new_free_rects = new_free_rects.concat(split_free_rect(free, used));
        });

        sheet.free_rects = prune_free_rects(new_free_rects);
    }

    function pack_maxrects(pieces, board_w_cm, board_h_cm, kerf_cm, heuristic) {
        const sheets = [];
        const unplaced = [];

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                const position = find_best_position_maxrects(sheet, piece, heuristic);

                if (position) {
                    place_piece_maxrects(sheet, piece, position, kerf_cm);
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = create_sheet(sheets.length + 1, board_w_cm, board_h_cm);
                const position = find_best_position_maxrects(sheet, piece, heuristic);

                if (position) {
                    place_piece_maxrects(sheet, piece, position, kerf_cm);
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        return { sheets, unplaced };
    }

    Object.assign(DCO, {
        contact_point_score,
        maxrects_score,
        find_best_position_maxrects,
        place_piece_maxrects,
        pack_maxrects
    });
})();
