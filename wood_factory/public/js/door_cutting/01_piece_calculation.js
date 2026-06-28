// =====================================================
// Piece Calculations
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { num, round, clone_pieces } = DCO;

    // =====================================================
    // Basic piece calculations
    // =====================================================

    function calculate_piece(row) {
        const width_cm = num(row.width_cm);
        const length_cm = num(row.length_cm);
        const qty = num(row.qty);

        let long_edges = 0;
        let width_edges = 0;

        if (row.edge_long_right) long_edges += 1;
        if (row.edge_long_left) long_edges += 1;
        if (row.edge_width_top) width_edges += 1;
        if (row.edge_width_bottom) width_edges += 1;

        row.area_m2 = round((width_cm * length_cm * qty) / 10000, 3);

        row.edge_meters = round(
            ((length_cm * long_edges) + (width_cm * width_edges)) * qty / 100,
            3
        );
    }

    function expand_pieces(rows) {
        const pieces = [];
        let serial = 1;

        (rows || []).forEach(row => {
            const qty = Math.max(0, Math.floor(num(row.qty)));
            const width_cm = num(row.width_cm);
            const length_cm = num(row.length_cm);

            if (!width_cm || !length_cm || !qty) return;

            for (let i = 1; i <= qty; i++) {
                pieces.push({
                    id: serial,
                    label: (row.piece_no ? row.piece_no : serial) + "." + i,
                    source_piece_no: row.piece_no || serial,
                    width_cm,
                    length_cm,
                    allow_rotation: row.allow_rotation ? 1 : 0,
                    area_m2: (width_cm * length_cm) / 10000,
                    notes: row.notes || ""
                });

                serial++;
            }
        });

        return pieces;
    }

    function orientations_for(piece) {
        const result = [
            { w: piece.width_cm, h: piece.length_cm, rotated: false }
        ];

        if (piece.allow_rotation && piece.width_cm !== piece.length_cm) {
            result.push({
                w: piece.length_cm,
                h: piece.width_cm,
                rotated: true
            });
        }

        return result;
    }

    function make_placed_piece(piece, x, y, w, h, rotated) {
        return {
            id: piece.id,
            label: piece.label,
            source_piece_no: piece.source_piece_no,
            x,
            y,
            w,
            h,
            original_w: piece.width_cm,
            original_h: piece.length_cm,
            rotated,
            area_m2: piece.area_m2,
            notes: piece.notes
        };
    }

    function sort_pieces(pieces, method) {
        const list = clone_pieces(pieces);

        if (method === "area_desc") {
            list.sort((a, b) => (b.width_cm * b.length_cm) - (a.width_cm * a.length_cm));
        } else if (method === "long_side_desc") {
            list.sort((a, b) => Math.max(b.width_cm, b.length_cm) - Math.max(a.width_cm, a.length_cm));
        } else if (method === "length_desc") {
            list.sort((a, b) => b.length_cm - a.length_cm);
        } else if (method === "width_desc") {
            list.sort((a, b) => b.width_cm - a.width_cm);
        } else if (method === "perimeter_desc") {
            list.sort((a, b) => ((b.width_cm + b.length_cm) * 2) - ((a.width_cm + a.length_cm) * 2));
        }

        return list;
    }

    function create_sheet(sheet_no, board_w_cm, board_h_cm) {
        return {
            sheet_no,
            w: board_w_cm,
            h: board_h_cm,
            pieces: [],
            free_rects: [
                { x: 0, y: 0, w: board_w_cm, h: board_h_cm }
            ]
        };
    }

    Object.assign(DCO, {
        calculate_piece,
        expand_pieces,
        orientations_for,
        make_placed_piece,
        sort_pieces,
        create_sheet
    });
})();
