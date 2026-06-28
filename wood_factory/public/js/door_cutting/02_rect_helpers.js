// =====================================================
// Rectangle Helpers
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    // =====================================================
    // Rectangle helpers
    // =====================================================

    function rect_intersects(a, b) {
        return !(
            b.x >= a.x + a.w ||
            b.x + b.w <= a.x ||
            b.y >= a.y + a.h ||
            b.y + b.h <= a.y
        );
    }

    function is_contained(a, b) {
        return (
            a.x >= b.x &&
            a.y >= b.y &&
            a.x + a.w <= b.x + b.w &&
            a.y + a.h <= b.y + b.h
        );
    }

    function split_free_rect(free, used) {
        const result = [];

        if (!rect_intersects(free, used)) {
            result.push(free);
            return result;
        }

        const min_size = 0.01;

        if (used.x > free.x) {
            result.push({
                x: free.x,
                y: free.y,
                w: used.x - free.x,
                h: free.h
            });
        }

        if (used.x + used.w < free.x + free.w) {
            result.push({
                x: used.x + used.w,
                y: free.y,
                w: (free.x + free.w) - (used.x + used.w),
                h: free.h
            });
        }

        if (used.y > free.y) {
            result.push({
                x: free.x,
                y: free.y,
                w: free.w,
                h: used.y - free.y
            });
        }

        if (used.y + used.h < free.y + free.h) {
            result.push({
                x: free.x,
                y: used.y + used.h,
                w: free.w,
                h: (free.y + free.h) - (used.y + used.h)
            });
        }

        return result.filter(r => r.w > min_size && r.h > min_size);
    }

    function prune_free_rects(free_rects) {
        const pruned = [];

        for (let i = 0; i < free_rects.length; i++) {
            let contained = false;

            for (let j = 0; j < free_rects.length; j++) {
                if (i !== j && is_contained(free_rects[i], free_rects[j])) {
                    contained = true;
                    break;
                }
            }

            if (!contained) pruned.push(free_rects[i]);
        }

        return pruned;
    }

    Object.assign(DCO, {
        rect_intersects,
        is_contained,
        split_free_rect,
        prune_free_rects
    });
})();
