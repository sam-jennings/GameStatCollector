"""Tests for data models."""

from __future__ import annotations

import json

import pytest

from collector.models import GameStats, ReelState, SpinResult, Win


# ---------------------------------------------------------------------------
# Win
# ---------------------------------------------------------------------------

class TestWin:
    def test_round_trip(self):
        win = Win(symbol="WILD", count=3, reels=[0, 1, 2], rows=[1, 1, 1], amount=5.0, line_index=0)
        assert Win.from_dict(win.to_dict()) == win

    def test_optional_line_index(self):
        win = Win(symbol="SCATTER", count=2, reels=[1, 3], rows=[0, 2], amount=0.0)
        d = win.to_dict()
        assert d["line_index"] is None
        restored = Win.from_dict(d)
        assert restored.line_index is None


# ---------------------------------------------------------------------------
# ReelState
# ---------------------------------------------------------------------------

class TestReelState:
    def _make(self) -> ReelState:
        return ReelState(symbols=[
            ["A", "B", "C"],
            ["D", "E", "F"],
            ["G", "H", "I"],
            ["J", "K", "L"],
            ["M", "N", "O"],
        ])

    def test_dimensions(self):
        rs = self._make()
        assert rs.num_reels == 5
        assert rs.num_rows == 3

    def test_round_trip(self):
        rs = self._make()
        assert ReelState.from_dict(rs.to_dict()) == rs


# ---------------------------------------------------------------------------
# SpinResult
# ---------------------------------------------------------------------------

class TestSpinResult:
    def _make(self) -> SpinResult:
        reel_state = ReelState(symbols=[["A", "B", "C"]] * 5)
        win = Win(symbol="A", count=3, reels=[0, 1, 2], rows=[0, 0, 0], amount=2.5)
        return SpinResult.create(
            spin_id=1,
            reel_state=reel_state,
            wins=[win],
            total_win=2.5,
            bet_amount=1.0,
        )

    def test_create_sets_timestamp(self):
        spin = self._make()
        assert spin.timestamp  # non-empty ISO timestamp

    def test_round_trip(self):
        spin = self._make()
        restored = SpinResult.from_dict(spin.to_dict())
        assert restored.spin_id == spin.spin_id
        assert restored.total_win == spin.total_win
        assert restored.reel_state == spin.reel_state
        assert restored.wins == spin.wins

    def test_to_dict_is_json_serialisable(self):
        spin = self._make()
        # Should not raise
        json.dumps(spin.to_dict())


# ---------------------------------------------------------------------------
# GameStats
# ---------------------------------------------------------------------------

class TestGameStats:
    def test_empty_round_trip(self):
        gs = GameStats()
        restored = GameStats.from_dict(gs.to_dict())
        assert restored.total_spins == 0
        assert restored.total_win_amount == 0.0

    def test_round_trip_with_data(self):
        gs = GameStats(
            total_spins=10,
            total_win_amount=25.0,
            win_frequency={"WILD": {3: 2, 4: 1}},
            symbol_position_counts={0: {0: {"WILD": 3}, 1: {"A": 7}}},
            reel_sequences={0: ["A", "B", "A", "C"]},
        )
        restored = GameStats.from_dict(gs.to_dict())
        assert restored.total_spins == 10
        assert restored.win_frequency["WILD"][3] == 2
        assert restored.symbol_position_counts[0][0]["WILD"] == 3
        assert restored.reel_sequences[0] == ["A", "B", "A", "C"]

    def test_to_json_is_valid(self):
        gs = GameStats(total_spins=5, total_win_amount=10.0)
        parsed = json.loads(gs.to_json())
        assert parsed["total_spins"] == 5
