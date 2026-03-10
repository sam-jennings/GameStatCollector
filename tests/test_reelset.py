"""Tests for reelset reconstruction and win stats analysis."""

from __future__ import annotations

import pytest

from analysis.reelset import ReelsetReconstructor
from analysis.win_stats import WinStatsAnalyser
from collector.models import GameStats, ReelState, SpinResult, Win
from collector.stats import StatsTracker
from tests.conftest import make_spin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_stats_from_spins(spins: list[SpinResult]) -> GameStats:
    tracker = StatsTracker()
    for spin in spins:
        tracker.record(spin)
    return tracker.stats


# ---------------------------------------------------------------------------
# WinStatsAnalyser
# ---------------------------------------------------------------------------

class TestWinStatsAnalyser:
    def test_empty_stats_returns_no_symbols(self):
        report = WinStatsAnalyser().analyse(GameStats())
        assert report.total_spins == 0
        assert report.symbol_summaries == []

    def test_rtp_calculation(self):
        stats = GameStats(total_spins=100, total_win_amount=90.0)
        report = WinStatsAnalyser().analyse(stats, bet_amount=1.0)
        assert report.rtp_observed == pytest.approx(0.90)

    def test_win_frequency_aggregated_correctly(self):
        spins = []
        for i in range(10):
            win = Win(symbol="WILD", count=3, reels=[0, 1, 2], rows=[1, 1, 1], amount=2.0)
            spins.append(make_spin(i, [["WILD", "A", "B"]] * 5, wins=[win], total_win=2.0))
        for i in range(10, 15):
            win = Win(symbol="WILD", count=4, reels=[0, 1, 2, 3], rows=[1, 1, 1, 1], amount=5.0)
            spins.append(make_spin(i, [["WILD", "A", "B"]] * 5, wins=[win], total_win=5.0))

        stats = _build_stats_from_spins(spins)
        report = WinStatsAnalyser().analyse(stats, bet_amount=1.0)

        wild_summary = next(s for s in report.symbol_summaries if s.symbol == "WILD")
        assert wild_summary.wins_by_count[3] == 10
        assert wild_summary.wins_by_count[4] == 5
        assert wild_summary.total_wins == 15

    def test_symbol_appearances_counted(self):
        symbols = [["A", "B", "C"]] * 5
        stats = _build_stats_from_spins([make_spin(i, symbols) for i in range(10)])
        report = WinStatsAnalyser().analyse(stats)

        a_summary = next((s for s in report.symbol_summaries if s.symbol == "A"), None)
        assert a_summary is not None
        # 10 spins × 5 reels = 50 appearances in row-0
        assert a_summary.total_appearances == 50

    def test_report_to_dict_serialisable(self):
        import json
        stats = GameStats(
            total_spins=5,
            total_win_amount=10.0,
            win_frequency={"A": {3: 2}},
            symbol_position_counts={0: {0: {"A": 5}}},
        )
        report = WinStatsAnalyser().analyse(stats)
        json.dumps(report.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# ReelsetReconstructor
# ---------------------------------------------------------------------------

class TestReelsetReconstructor:
    def test_empty_stats_returns_empty_reels(self):
        report = ReelsetReconstructor().reconstruct(GameStats())
        assert report.reels == []

    def test_symbol_weights_sum_to_one(self):
        symbols = [["A", "B", "C"]] * 5
        stats = _build_stats_from_spins([make_spin(i, symbols) for i in range(20)])
        report = ReelsetReconstructor().reconstruct(stats)

        for reel in report.reels:
            total = sum(reel.symbol_weights.values())
            assert total == pytest.approx(1.0, abs=1e-6)

    def test_known_strip_reconstruction(self):
        """With a deterministic repeating strip, confidence should be high."""
        # Simulate a reel strip: A B C A B C … (only middle-row observations)
        strip = ["A", "B", "C", "D", "E"] * 100  # 500 observations
        reel_sequences = {0: strip}

        # Build position counts from the middle row
        symbol_counts = {}
        for sym in strip:
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1

        stats = GameStats(
            total_spins=len(strip),
            reel_sequences=reel_sequences,
            symbol_position_counts={0: {1: symbol_counts}},  # row 1 = middle
        )
        report = ReelsetReconstructor().reconstruct(stats)
        assert len(report.reels) == 1
        reel = report.reels[0]
        # All 5 symbols should be present
        assert set(reel.symbol_weights.keys()) == {"A", "B", "C", "D", "E"}
        # Confidence should be high (near 1.0) for a perfectly regular strip
        assert reel.confidence > 0.8

    def test_report_to_json_serialisable(self):
        import json
        symbols = [["X", "Y", "Z"]] * 3
        stats = _build_stats_from_spins([make_spin(i, symbols) for i in range(5)])
        report = ReelsetReconstructor().reconstruct(stats)
        json.loads(report.to_json())  # must not raise

    def test_single_symbol_reel(self):
        """Edge case: all symbols on a reel are the same."""
        stats = GameStats(
            total_spins=10,
            reel_sequences={0: ["A"] * 10},
            symbol_position_counts={0: {1: {"A": 10}}},
        )
        report = ReelsetReconstructor().reconstruct(stats)
        assert report.reels[0].symbol_weights["A"] == pytest.approx(1.0)
