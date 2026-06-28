// =====================================================
// Constants + Common Utilities
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    // هذا الملف يجب تحميله أولًا لأنه يحتوي الثوابت والدوال العامة.
    // Guillotine Short Axis
    // Guillotine Long Axis
    // Guillotine Best Area Fit
    // Guillotine Best Short Side Fit
    // Guillotine Best Long Side Fit
    // Skyline Bottom Left
    // Skyline Best Fit
    // =====================================================

    const EDGE_RATES = {
        "قشاط 2سم عادي": 0.5,
        "قشاط 4سم عادي": 1,
        "قشاط 2سم لميع": 1,
        "قشاط 4سم لميع": 2,
        "قشاط 2سم عادي يدوي": 1,
        "قشاط 4سم عادي يدوي": 2,
        "قشاط 2سم ذهبي": 1.25,
        "قشاط 4سم ذهبي": 2.5,
        "قشاط 2سم ذهبي يدوي": 2.5,
        "قشاط 4سم ذهبي يدوي": 5,
        "قشاط 2سم لميع يدوي": 2,
        "قشاط 4سم لميع يدوي": 4
    };

    const EDGE_OPTIONS = Object.keys(EDGE_RATES);

    const PACKING_OPTIONS = [
        "Auto",
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

    function num(value) {
        if (value === null || value === undefined) return 0;
        return parseFloat(String(value).replace(/,/g, "")) || 0;
    }

    function round(value, decimals = 3) {
        const factor = Math.pow(10, decimals);
        return Math.round(num(value) * factor) / factor;
    }

    function escape_html(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function clone_pieces(pieces) {
        return pieces.map(p => Object.assign({}, p));
    }

    function normalize_mode(mode) {
        const map = {
            "تلقائي": "Auto",
            "MaxRects Area": "MaxRects Best Area",
            "MaxRects Long Side": "MaxRects Best Short Side"
        };

        return map[mode] || mode || "Auto";
    }

    Object.assign(DCO, {
        EDGE_RATES,
        EDGE_OPTIONS,
        PACKING_OPTIONS,
        num,
        round,
        escape_html,
        clone_pieces,
        normalize_mode
    });
})();
