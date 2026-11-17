#!/usr/bin/env python3
"""Regression tests for the feature/outcome and multiple-testing helpers."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate import bh_adjust
from signals import add_outcomes


class DeadOutcomeTest(unittest.TestCase):
    def test_launch_without_post_window_trade_is_dead(self):
        features = pd.DataFrame({"launch_time": [100, 100]}, index=["a", "b"])
        trades = pd.DataFrame(
            {
                "mint": ["a", "a"],
                "trade_time": [110, 230],
                "price": [1.0, 0.5],
                "rel_seconds": [10, 130],
            }
        )
        migrations = pd.DataFrame({"mint": [], "rel_seconds": []})

        out = add_outcomes(features, trades, migrations)

        self.assertFalse(bool(out.loc["a", "dead_1h"]))
        self.assertTrue(bool(out.loc["b", "dead_1h"]))
        self.assertTrue(pd.isna(out.loc["b", "rug_1h"]))


class BHAdjustTest(unittest.TestCase):
    def test_nan_does_not_poison_other_adjustments(self):
        adjusted = bh_adjust([0.01, 0.02, float("nan")])

        self.assertFalse(np.isnan(adjusted[0]))
        self.assertFalse(np.isnan(adjusted[1]))
        self.assertTrue(np.isnan(adjusted[2]))

    def test_empty_input(self):
        self.assertEqual(bh_adjust([]), [])


if __name__ == "__main__":
    unittest.main()
