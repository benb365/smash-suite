import unittest
from ranges import compact_ranges

class RangesTests(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(compact_ranges([(1, 4), (2, 6)]), [(1, 6)])

    def test_empty(self):
        self.assertEqual(compact_ranges([]), [])

    def test_touching_duplicates_and_zero_length(self):
        self.assertEqual(
            compact_ranges([(3, 3), (1, 2), (2, 3), (1, 2)]),
            [(1, 3)],
        )

    def test_does_not_modify_input(self):
        ranges = [(3, 4), (0, 1)]
        original = ranges.copy()

        self.assertEqual(compact_ranges(ranges), [(0, 1), (3, 4)])
        self.assertEqual(ranges, original)

    def test_rejects_reversed_range(self):
        with self.assertRaises(ValueError):
            compact_ranges([(0, 1), (3, 2)])

if __name__ == "__main__":
    unittest.main()
