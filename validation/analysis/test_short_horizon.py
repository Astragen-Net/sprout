#!/usr/bin/env python3
"""Tests for the short-horizon dump harness."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from short_horizon_dump import add_labels, parse_windows


class ParseWindowsTest(unittest.TestCase):
    def test_sorts_and_deduplicates(self):
        self.assertEqual(parse_windows("15,5,5,30"), [5, 15, 30])


class AddLabelsTest(unittest.TestCase):
    def test_dump_no_trade_and_non_dump(self):
        frame = pd.DataFrame(
            {
                "price_60s": [1.0, 1.0, 1.0],
                "min_5": [0.4, 0.6, np.nan],
            }
        )
        result = add_labels(frame, [5], 0.5)

        self.assertEqual(result["dump_5"].tolist(), [True, False, False])
        self.assertEqual(result["no_trade_5"].tolist(), [False, False, True])


if __name__ == "__main__":
    unittest.main()
