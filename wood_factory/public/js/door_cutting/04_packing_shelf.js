// =====================================================
// Shelf Packing
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { orientations_for, make_placed_piece } = DCO;

    // =====================================================
    // Shelf Packing
    // =====================================================

    function pack_shelf_horizontal(pieces, board_w_cm, board_h_cm, kerf_cm) {
        const sheets = [];
        const unplaced = [];

        function new_sheet() {
            return {
                sheet_no: sheets.length + 1,
                w: board_w_cm,
                h: board_h_cm,
                pieces: [],
                _x: 0,
                _y: 0,
                _row_h: 0
            };
        }

        function try_place(sheet, piece) {
            for (const o of orientations_for(piece)) {
                if (sheet._x + o.w <= board_w_cm && sheet._y + o.h <= board_h_cm) {
                    sheet.pieces.push(make_placed_piece(piece, sheet._x, sheet._y, o.w, o.h, o.rotated));
                    sheet._x += o.w + kerf_cm;
                    sheet._row_h = Math.max(sheet._row_h, o.h + kerf_cm);
                    return true;
                }
            }

            sheet._x = 0;
            sheet._y += sheet._row_h;
            sheet._row_h = 0;

            for (const o of orientations_for(piece)) {
                if (sheet._x + o.w <= board_w_cm && sheet._y + o.h <= board_h_cm) {
                    sheet.pieces.push(make_placed_piece(piece, sheet._x, sheet._y, o.w, o.h, o.rotated));
                    sheet._x += o.w + kerf_cm;
                    sheet._row_h = Math.max(sheet._row_h, o.h + kerf_cm);
                    return true;
                }
            }

            return false;
        }

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                if (try_place(sheet, piece)) {
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = new_sheet();

                if (try_place(sheet, piece)) {
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        sheets.forEach(s => {
            delete s._x;
            delete s._y;
            delete s._row_h;
        });

        return { sheets, unplaced };
    }

    function pack_shelf_vertical(pieces, board_w_cm, board_h_cm, kerf_cm) {
        const sheets = [];
        const unplaced = [];

        function new_sheet() {
            return {
                sheet_no: sheets.length + 1,
                w: board_w_cm,
                h: board_h_cm,
                pieces: [],
                _x: 0,
                _y: 0,
                _col_w: 0
            };
        }

        function try_place(sheet, piece) {
            for (const o of orientations_for(piece)) {
                if (sheet._x + o.w <= board_w_cm && sheet._y + o.h <= board_h_cm) {
                    sheet.pieces.push(make_placed_piece(piece, sheet._x, sheet._y, o.w, o.h, o.rotated));
                    sheet._y += o.h + kerf_cm;
                    sheet._col_w = Math.max(sheet._col_w, o.w + kerf_cm);
                    return true;
                }
            }

            sheet._y = 0;
            sheet._x += sheet._col_w;
            sheet._col_w = 0;

            for (const o of orientations_for(piece)) {
                if (sheet._x + o.w <= board_w_cm && sheet._y + o.h <= board_h_cm) {
                    sheet.pieces.push(make_placed_piece(piece, sheet._x, sheet._y, o.w, o.h, o.rotated));
                    sheet._y += o.h + kerf_cm;
                    sheet._col_w = Math.max(sheet._col_w, o.w + kerf_cm);
                    return true;
                }
            }

            return false;
        }

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                if (try_place(sheet, piece)) {
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = new_sheet();

                if (try_place(sheet, piece)) {
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        sheets.forEach(s => {
            delete s._x;
            delete s._y;
            delete s._col_w;
        });

        return { sheets, unplaced };
    }

    function pack_shelf_first_fit(pieces, board_w_cm, board_h_cm, kerf_cm) {
        const sheets = [];
        const unplaced = [];

        function new_sheet() {
            return {
                sheet_no: sheets.length + 1,
                w: board_w_cm,
                h: board_h_cm,
                pieces: [],
                shelves: []
            };
        }

        function try_place(sheet, piece) {
            for (const shelf of sheet.shelves) {
                for (const o of orientations_for(piece)) {
                    if (o.h <= shelf.h && shelf.x + o.w <= board_w_cm) {
                        sheet.pieces.push(make_placed_piece(piece, shelf.x, shelf.y, o.w, o.h, o.rotated));
                        shelf.x += o.w + kerf_cm;
                        return true;
                    }
                }
            }

            let current_y = 0;
            sheet.shelves.forEach(s => {
                current_y = Math.max(current_y, s.y + s.h + kerf_cm);
            });

            for (const o of orientations_for(piece)) {
                if (current_y + o.h <= board_h_cm && o.w <= board_w_cm) {
                    sheet.pieces.push(make_placed_piece(piece, 0, current_y, o.w, o.h, o.rotated));
                    sheet.shelves.push({
                        y: current_y,
                        h: o.h,
                        x: o.w + kerf_cm
                    });
                    return true;
                }
            }

            return false;
        }

        pieces.forEach(piece => {
            let placed = false;

            for (const sheet of sheets) {
                if (try_place(sheet, piece)) {
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                const sheet = new_sheet();

                if (try_place(sheet, piece)) {
                    sheets.push(sheet);
                } else {
                    unplaced.push(piece);
                }
            }
        });

        sheets.forEach(s => delete s.shelves);

        return { sheets, unplaced };
    }

    function pack_shelf_next_fit(pieces, board_w_cm, board_h_cm, kerf_cm) {
        const sheets = [];
        const unplaced = [];

        let sheet = null;
        let x = 0;
        let y = 0;
        let row_h = 0;

        function start_new_sheet() {
            sheet = {
                sheet_no: sheets.length + 1,
                w: board_w_cm,
                h: board_h_cm,
                pieces: []
            };
            sheets.push(sheet);
            x = 0;
            y = 0;
            row_h = 0;
        }

        function place(piece, o) {
            sheet.pieces.push(make_placed_piece(piece, x, y, o.w, o.h, o.rotated));
            x += o.w + kerf_cm;
            row_h = Math.max(row_h, o.h + kerf_cm);
        }

        pieces.forEach(piece => {
            if (!sheet) start_new_sheet();

            let placed = false;

            for (const o of orientations_for(piece)) {
                if (x + o.w <= board_w_cm && y + o.h <= board_h_cm) {
                    place(piece, o);
                    placed = true;
                    break;
                }
            }

            if (!placed) {
                x = 0;
                y += row_h;
                row_h = 0;

                for (const o of orientations_for(piece)) {
                    if (x + o.w <= board_w_cm && y + o.h <= board_h_cm) {
                        place(piece, o);
                        placed = true;
                        break;
                    }
                }
            }

            if (!placed) {
                start_new_sheet();

                for (const o of orientations_for(piece)) {
                    if (x + o.w <= board_w_cm && y + o.h <= board_h_cm) {
                        place(piece, o);
                        placed = true;
                        break;
                    }
                }
            }

            if (!placed) unplaced.push(piece);
        });

        return { sheets, unplaced };
    }

    Object.assign(DCO, {
        pack_shelf_horizontal,
        pack_shelf_vertical,
        pack_shelf_first_fit,
        pack_shelf_next_fit
    });
})();
