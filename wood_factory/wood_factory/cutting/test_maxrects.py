import unittest

from wood_factory.wood_factory.cutting.maxrects import optimize


class TestMaxRects(unittest.TestCase):
    def test_expands_across_boards_without_overlap(self):
        pieces = [
            {"piece_id": "A", "source_row": 1, "part_name": "Door A", "width": 600, "height": 400, "allow_rotation": True, "grain_direction": "Any"},
            {"piece_id": "B", "source_row": 2, "part_name": "Door B", "width": 600, "height": 400, "allow_rotation": True, "grain_direction": "Any"},
            {"piece_id": "C", "source_row": 3, "part_name": "Door C", "width": 600, "height": 400, "allow_rotation": True, "grain_direction": "Any"},
        ]
        result = optimize(1000, 1000, pieces, kerf=3, algorithm="Auto")
        self.assertEqual(len(result["boards"]), 2)
        self.assertEqual(sum(len(board["placements"]) for board in result["boards"]), 3)

    def test_rotation_is_not_used_when_grain_is_constrained(self):
        pieces = [{"piece_id": "A", "source_row": 1, "part_name": "Door", "width": 900, "height": 500, "allow_rotation": True, "grain_direction": "Along Width"}]
        with self.assertRaises(ValueError):
            optimize(600, 1000, pieces, kerf=3, algorithm="MaxRects Best Short Side Fit")

    def test_kerf_prevents_touching_pieces_from_fitting(self):
        pieces = [
            {"piece_id": "A", "source_row": 1, "part_name": "A", "width": 500, "height": 1000, "allow_rotation": False, "grain_direction": "Any"},
            {"piece_id": "B", "source_row": 2, "part_name": "B", "width": 500, "height": 1000, "allow_rotation": False, "grain_direction": "Any"},
        ]
        result = optimize(1000, 1000, pieces, kerf=3, algorithm="MaxRects Best Area Fit")
        self.assertEqual(len(result["boards"]), 2)


if __name__ == "__main__":
    unittest.main()
