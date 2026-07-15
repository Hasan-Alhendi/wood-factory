from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


HEURISTICS = {
    "MaxRects Best Short Side Fit": "bssf",
    "MaxRects Best Area Fit": "baf",
    "MaxRects Bottom Left": "bl",
}


def optimize(board_width, board_height, pieces, kerf=3, algorithm="Auto"):
    algorithms = list(HEURISTICS) if algorithm == "Auto" else [algorithm]
    results = [_pack(board_width, board_height, pieces, kerf, name) for name in algorithms]
    return min(results, key=lambda result: (len(result["boards"]), result["waste_percent"], result["algorithm"]))


def _pack(board_width, board_height, pieces, kerf, algorithm):
    if algorithm not in HEURISTICS:
        raise ValueError(f"Unsupported nesting algorithm: {algorithm}")
    ordered = sorted(pieces, key=lambda p: (-(p["width"] * p["height"]), -max(p["width"], p["height"]), p["piece_id"]))
    boards = []
    for piece in ordered:
        placed = False
        for board in boards:
            candidate = _find_position(board["free"], piece, kerf, HEURISTICS[algorithm])
            if candidate:
                _place(board, piece, candidate, kerf)
                placed = True
                break
        if not placed:
            board = {"free": [Rect(0, 0, board_width, board_height)], "placements": []}
            candidate = _find_position(board["free"], piece, kerf, HEURISTICS[algorithm])
            if not candidate:
                raise ValueError(f'Piece {piece["piece_id"]} does not fit the board')
            _place(board, piece, candidate, kerf)
            boards.append(board)
    used = sum(p["width"] * p["height"] for b in boards for p in b["placements"])
    total = len(boards) * board_width * board_height
    output_boards = []
    for board in boards:
        reusable = _reusable_free_rectangles(board_width, board_height, board["placements"], kerf)
        output_boards.append({
            "placements": board["placements"],
            "free_rectangles": [
                {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height}
                for rect in reusable
            ],
        })
    return {
        "algorithm": algorithm,
        "boards": output_boards,
        "waste_percent": round(((total - used) / total) * 100, 2) if total else 0,
    }


def _find_position(free_rects, piece, kerf, heuristic):
    candidates = []
    orientations = [(piece["width"], piece["height"], False)]
    if piece.get("allow_rotation") and piece["width"] != piece["height"] and piece.get("grain_direction", "Any") == "Any":
        orientations.append((piece["height"], piece["width"], True))
    for free in free_rects:
        for width, height, rotated in orientations:
            if width <= free.width and height <= free.height:
                dw, dh = free.width - width, free.height - height
                if heuristic == "bssf":
                    score = (min(dw, dh), max(dw, dh), free.y, free.x)
                elif heuristic == "baf":
                    score = (free.width * free.height - width * height, min(dw, dh), free.y, free.x)
                else:
                    score = (free.y + height, free.x, min(dw, dh))
                candidates.append((score, free, width, height, rotated))
    return min(candidates, key=lambda c: c[0]) if candidates else None


def _place(board, piece, candidate, kerf):
    _, free, width, height, rotated = candidate
    x, y = free.x, free.y
    occupied = Rect(x, y, min(width + kerf, free.width), min(height + kerf, free.height))
    new_free = []
    for free_rect in board["free"]:
        new_free.extend(_split_free_rect(free_rect, occupied)) if _intersects(free_rect, occupied) else new_free.append(free_rect)
    board["free"] = _prune(new_free)
    edges = _rotate_edges(piece, rotated)
    board["placements"].append({"piece_id": piece["piece_id"], "source_row": piece["source_row"], "part_name": piece["part_name"], "x": x, "y": y, "width": width, "height": height, "rotated": rotated, **edges})


def _reusable_free_rectangles(board_width, board_height, placements, kerf):
    free_rects = [Rect(0, 0, board_width, board_height)]
    for placement in placements:
        occupied = Rect(
            placement["x"],
            placement["y"],
            min(placement["width"] + kerf, board_width - placement["x"]),
            min(placement["height"] + kerf, board_height - placement["y"]),
        )
        next_free = []
        for free in free_rects:
            next_free.extend(_subtract_non_overlapping(free, occupied))
        free_rects = next_free
    return sorted(_prune(free_rects), key=lambda rect: (rect.y, rect.x, -rect.width * rect.height))


def _subtract_non_overlapping(free, used):
    if not _intersects(free, used):
        return [free]
    left = max(free.x, used.x)
    top = max(free.y, used.y)
    right = min(free.x + free.width, used.x + used.width)
    bottom = min(free.y + free.height, used.y + used.height)
    rects = []
    if top > free.y:
        rects.append(Rect(free.x, free.y, free.width, top - free.y))
    if bottom < free.y + free.height:
        rects.append(Rect(free.x, bottom, free.width, free.y + free.height - bottom))
    middle_height = bottom - top
    if middle_height > 0 and left > free.x:
        rects.append(Rect(free.x, top, left - free.x, middle_height))
    if middle_height > 0 and right < free.x + free.width:
        rects.append(Rect(right, top, free.x + free.width - right, middle_height))
    return [rect for rect in rects if rect.width > 0 and rect.height > 0]


def _rotate_edges(piece, rotated):
    edges = {"edge_top": bool(piece.get("edge_top")), "edge_right": bool(piece.get("edge_right")), "edge_bottom": bool(piece.get("edge_bottom")), "edge_left": bool(piece.get("edge_left"))}
    if not rotated:
        return edges
    return {"edge_top": edges["edge_left"], "edge_right": edges["edge_top"], "edge_bottom": edges["edge_right"], "edge_left": edges["edge_bottom"]}


def _intersects(a, b):
    return not (b.x >= a.x + a.width or b.x + b.width <= a.x or b.y >= a.y + a.height or b.y + b.height <= a.y)


def _split_free_rect(free, used):
    rects = []
    if used.x > free.x:
        rects.append(Rect(free.x, free.y, used.x - free.x, free.height))
    if used.x + used.width < free.x + free.width:
        rects.append(Rect(used.x + used.width, free.y, free.x + free.width - used.x - used.width, free.height))
    if used.y > free.y:
        rects.append(Rect(free.x, free.y, free.width, used.y - free.y))
    if used.y + used.height < free.y + free.height:
        rects.append(Rect(free.x, used.y + used.height, free.width, free.y + free.height - used.y - used.height))
    return [r for r in rects if r.width > 0 and r.height > 0]


def _prune(rects):
    return [rect for i, rect in enumerate(rects) if not any(i != j and _contains(other, rect) for j, other in enumerate(rects))]


def _contains(a, b):
    return a.x <= b.x and a.y <= b.y and a.x + a.width >= b.x + b.width and a.y + a.height >= b.y + b.height
