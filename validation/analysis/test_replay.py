#!/usr/bin/env python3
"""Tests for the replay backtest helpers."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_backtest import net_return, simulate_mint


def trade_frame(rows):
    frame = pd.DataFrame(
        rows,
        columns=["trade_time", "slot", "tx_index", "ix_path", "price", "rel_seconds"],
    )
    return frame


class NetReturnTest(unittest.TestCase):
    def test_no_costs(self):
        self.assertAlmostEqual(net_return(1.0, 2.0, 0, 0), 1.0)

    def test_fees_and_slippage_on_both_sides(self):
        self.assertAlmostEqual(net_return(1.0, 2.0, 100, 100), 0.9215, places=3)


class SimulateMintTest(unittest.TestCase):
    def test_enters_after_delay_and_exits_at_horizon(self):
        frame = trade_frame(
            [
                (61, 1, 0, 0, 1.0, 61),
                (70, 1, 1, 0, 2.0, 70),
                (100, 1, 2, 0, 3.0, 100),
                (200, 1, 3, 0, 4.0, 200),
            ]
        )
        result = simulate_mint(frame, 5, 300, 3_600, 0.0, 0, 0)

        self.assertTrue(result["filled"])
        self.assertEqual(result["reason"], "horizon")
        self.assertEqual(result["entry_time"], 70)
        self.assertEqual(result["exit_time"], 200)
        self.assertAlmostEqual(result["net_return"], 1.0)

    def test_no_entry_outside_entry_window(self):
        frame = trade_frame(
            [
                (61, 1, 0, 0, 1.0, 61),
                (64, 1, 1, 0, 1.0, 64),
            ]
        )
        result = simulate_mint(frame, 5, 300, 3_600, 0.0, 0, 0)

        self.assertFalse(result["filled"])
        self.assertEqual(result["reason"], "no_entry")

    def test_no_post_entry_trade_is_unsellable(self):
        frame = trade_frame([(70, 1, 0, 0, 1.0, 70)])
        result = simulate_mint(frame, 5, 300, 3_600, 0.0, 0, 0)

        self.assertTrue(result["filled"])
        self.assertEqual(result["reason"], "unsellable")
        self.assertEqual(result["net_return"], -1.0)

    def test_stop_exits_at_first_trade_below_threshold(self):
        frame = trade_frame(
            [
                (70, 1, 0, 0, 1.0, 70),
                (100, 1, 1, 0, 0.4, 100),
                (200, 1, 2, 0, 0.5, 200),
            ]
        )
        result = simulate_mint(frame, 5, 300, 3_600, 0.5, 0, 0)

        self.assertTrue(result["filled"])
        self.assertEqual(result["reason"], "stop")
        self.assertEqual(result["exit_time"], 100)
        self.assertAlmostEqual(result["net_return"], -0.6)


if __name__ == "__main__":
    unittest.main()
