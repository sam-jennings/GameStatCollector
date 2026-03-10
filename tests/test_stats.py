"""Tests for StatsTracker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from collector.models import GameStats, ReelState, SpinResult, Win
from collector.stats import StatsTracker
from tests.conftest import make_spin


class TestStatsTracker:
    def test_record_increments_total_spins(self):
        tracker = StatsTracker()
        for i in range(5):
            tracker.record(make_spin(i, [["A", "B", "C"]] * 5))
        assert tracker.stats.total_spins == 5

    def test_record_accumulates_win_amount(self):
        tracker = StatsTracker()
        win = Win(symbol="WILD", count=3, reels=[0, 1, 2], rows=[1, 1, 1], amount=2.0)
        tracker.record(make_spin(0, [["WILD", "A", "B"]] * 5, wins=[win], total_win=2.0))
        tracker.record(make_spin(1, [["A", "B", "C"]] * 5, total_win=0.0))
        assert tracker.stats.total_win_amount == pytest.approx(2.0)

    def test_record_tracks_win_frequency(self):
        tracker = StatsTracker()
        w3 = Win(symbol="WILD", count=3, reels=[0, 1, 2], rows=[1, 1, 1], amount=2.0)
        w4 = Win(symbol="WILD", count=4, reels=[0, 1, 2, 3], rows=[1, 1, 1, 1], amount=5.0)
        tracker.record(make_spin(0, [["WILD"] * 3] * 5, wins=[w3], total_win=2.0))
        tracker.record(make_spin(1, [["WILD"] * 3] * 5, wins=[w4], total_win=5.0))
        tracker.record(make_spin(2, [["WILD"] * 3] * 5, wins=[w3], total_win=2.0))

        assert tracker.stats.win_frequency["WILD"][3] == 2
        assert tracker.stats.win_frequency["WILD"][4] == 1

    def test_record_tracks_symbol_position_counts(self):
        tracker = StatsTracker()
        symbols = [["A", "B", "C"]] * 5  # 5 reels, 3 rows each
        tracker.record(make_spin(0, symbols))
        tracker.record(make_spin(1, symbols))

        # Reel 0, row 0 should have "A" counted twice
        assert tracker.stats.symbol_position_counts[0][0]["A"] == 2
        assert tracker.stats.symbol_position_counts[0][1]["B"] == 2
        assert tracker.stats.symbol_position_counts[0][2]["C"] == 2

    def test_record_tracks_reel_sequences(self):
        tracker = StatsTracker()
        # Middle row (index 1) of 3-row reel
        symbols_a = [["X", "A", "X"]] * 5
        symbols_b = [["X", "B", "X"]] * 5
        tracker.record(make_spin(0, symbols_a))
        tracker.record(make_spin(1, symbols_b))

        assert tracker.stats.reel_sequences[0] == ["A", "B"]

    def test_save_and_load_roundtrip(self):
        tracker = StatsTracker()
        win = Win(symbol="S1", count=3, reels=[0, 1, 2], rows=[1, 1, 1], amount=3.0)
        tracker.record(make_spin(0, [["S1", "S2", "S3"]] * 5, wins=[win], total_win=3.0))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stats.json"
            tracker.save(path)
            loaded = StatsTracker.load(path)

        assert loaded.stats.total_spins == 1
        assert loaded.stats.win_frequency["S1"][3] == 1
        assert loaded.stats.total_win_amount == pytest.approx(3.0)
