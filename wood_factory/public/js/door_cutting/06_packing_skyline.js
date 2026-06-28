// =====================================================
// Skyline Packing
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { round, orientations_for, make_placed_piece } = DCO;

    // =====================================================
    // Skyline Packing
    // =====================================================

    function create_skyline_sheet(sheet_no, board_w_cm, board_h_cm) {
        return {
            sheet_no,
            w: board_w_cm,
            h: board_h_cm,
            pieces: [],
            skyline: [{ x: 0, y: 0, w: board_w_cm }]
        };
    }

    function skyline_rect_fits(sheet, index, w, h) {
        const x = sheet.skyline[index].x;

        if (x + w > sheet.w) return null;

        let width_left = w;
        let y = sheet.skyline[index].y;
        let i = index;

        while (width_left > 0) {
            if (i >= sheet.skyline.length) return null;

            y = Math.max(y, sheet.skyline[i].y);

            if (y + h > sheet.h) return null;

            width_left -= sheet.skyline[i].w;
            i++;
        }

        return { x, y };
    }

    function skyline_find_position(sheet, piece, mode) {
        let best = null;

        for (let i = 0; i < sheet.skyline.length; i++) {
            for (const o of orientations_for(piece)) {
                const pos = skyline_rect_fits(sheet, i, o.w, o.h);

                if (!pos) continue;

                let score;

                if (mode === "best_fit") {
                    const waste = pos.y * sheet.w;
                    score = pos.y * 100000 + waste + pos.x;
                } else {
                    score = pos.y * 100000 + pos.x;
                }

                if (!best || score < best.score) {
                    best = {
                        index: i,
                        x: pos.x,
                        y: pos.y,
                        w: o.w,
                        h: o.h,
                        rotated: o.rotated,
                        score
                    };
                }
            }
        }

        return best;
    }

    function skyline_merge(sheet) {
        for (let i = 0; i < sheet.skyline.length - 1; i++) {
            if (round(sheet.skyline[i].y, 3) === round(sheet.skyline[i + 1].y, 3)) {
                sheet.skyline[i].w += sheet.skyline[i + 1].w;
                sheet.skyline.splice(i + 1, 1);
                i--;
            }
        }
    }

    function skyline_add_level(sheet, pos, kerf_cm) {
        const new_node = {
            x: pos.x,
            y: pos.y + pos.h + kerf_cm,
            w: Math.min(pos.w + kerf_cm, sheet.w - pos.x)
        };

        sheet.skyline.splice(pos.index, 0, new_node);

        for (let i = pos.index + 1; i < sheet.skyline.length; i++) {
            const prev = sheet.skyline[i - 1];
            const curr = sheet.skyline[i];

            if (curr.x < prev.x + prev.w) {
                const shrink = prev.x + prev.w - curr.x;
                curr.x += shrink;
                curr.w -= shrink;

                if (curr.w <= 0) {
                    sheet.skyline.splice(i, 1);
                    i--;
                } else {
                    break;
                }
            } else {
                break;
            }
        }

        skyline_merge(sheet);
    }

    function pack_skyline(pieces, board_w_cm, board_h_cm, kerf_cm, mode) {
        const sheets = [];
        const unplaced = [];

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                const pos = skyline_find_position(sheet, piece, mode);

                if (pos) {
                    sheet.pieces.push(make_placed_piece(piece, pos.x, pos.y, pos.w, pos.h, pos.rotated));
                    skyline_add_level(sheet, pos, kerf_cm);
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = create_skyline_sheet(sheets.length + 1, board_w_cm, board_h_cm);
                const pos = skyline_find_position(sheet, piece, mode);

                if (pos) {
                    sheet.pieces.push(make_placed_piece(piece, pos.x, pos.y, pos.w, pos.h, pos.rotated));
                    skyline_add_level(sheet, pos, kerf_cm);
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        sheets.forEach(s => delete s.skyline);

        return { sheets, unplaced };
    }

    Object.assign(DCO, {
        create_skyline_sheet,
        skyline_rect_fits,
        skyline_find_position,
        skyline_merge,
        skyline_add_level,
        pack_skyline
    });
})();
