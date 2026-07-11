frappe.ui.form.on("Board Layout", {
    refresh(frm) {
        render_board_layout(frm);
    },
    placements_add(frm) {
        render_board_layout(frm);
    },
    placements_remove(frm) {
        render_board_layout(frm);
    },
});

function render_board_layout(frm) {
    const field = frm.fields_dict.layout_preview;
    if (!field || !frm.doc.board_width_mm || !frm.doc.board_height_mm) return;

    const boardWidth = flt(frm.doc.board_width_mm);
    const boardHeight = flt(frm.doc.board_height_mm);
    const placements = frm.doc.placements || [];
    const maxPreviewWidth = 1100;
    const maxPreviewHeight = 650;
    const scale = Math.min(maxPreviewWidth / boardWidth, maxPreviewHeight / boardHeight, 1);
    const width = Math.max(boardWidth * scale, 320);
    const height = Math.max(boardHeight * scale, 180);

    const pieces = placements.map((piece, index) => {
        const x = flt(piece.x_mm) * scale;
        const y = flt(piece.y_mm) * scale;
        const w = flt(piece.width_mm) * scale;
        const h = flt(piece.height_mm) * scale;
        const label = frappe.utils.escape_html(piece.part_name || piece.piece_id || __("Piece"));
        const size = `${format_number(piece.width_mm)} × ${format_number(piece.height_mm)} mm`;
        const rotation = cint(piece.rotated) ? ` · ${__("Rotated")}` : "";
        const hue = (index * 47) % 360;
        return `
            <div class="wf-piece" title="${label} · ${size}${rotation}"
                style="left:${x}px;top:${y}px;width:${w}px;height:${h}px;background:hsl(${hue} 55% 84%);border-color:hsl(${hue} 45% 38%);">
                <strong>${label}</strong>
                <span>${size}</span>
                <small>${piece.piece_id || ""}${rotation}</small>
            </div>`;
    }).join("");

    field.$wrapper.html(`
        <style>
            .wf-layout-wrap{overflow:auto;padding:12px 0 18px}
            .wf-layout-meta{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px;font-size:13px}
            .wf-board{position:relative;box-sizing:content-box;background:#f4ead7;border:3px solid #5c4630;box-shadow:0 3px 12px rgba(0,0,0,.12);width:${width}px;height:${height}px}
            .wf-piece{position:absolute;box-sizing:border-box;border:2px solid;overflow:hidden;padding:4px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;line-height:1.15;color:#222}
            .wf-piece strong{font-size:12px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
            .wf-piece span,.wf-piece small{font-size:10px;margin-top:2px}
        </style>
        <div class="wf-layout-wrap">
            <div class="wf-layout-meta">
                <b>${__("Board")} #${frm.doc.board_no || "-"}</b>
                <span>${format_number(boardWidth)} × ${format_number(boardHeight)} mm</span>
                <span>${__("Pieces")}: ${placements.length}</span>
                <span>${__("Waste")}: ${format_number(frm.doc.waste_percent || 0, 2)}%</span>
            </div>
            <div class="wf-board">${pieces}</div>
        </div>`);
}

function format_number(value, decimals = 0) {
    return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: decimals });
}
