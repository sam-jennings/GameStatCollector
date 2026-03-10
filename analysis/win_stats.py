"""Win statistics analysis.

Reads :class:`~collector.models.GameStats` and produces human-readable
reports showing win frequency broken down by:

* symbol name
* win length (2-, 3-, 4-, or 5-of-a-kind)
* per-reel symbol frequency (useful for spotting high-weight symbols)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from collector.models import GameStats


@dataclass
class SymbolWinSummary:
    """Win statistics for a single symbol."""

    symbol: str
    wins_by_count: dict[int, int] = field(default_factory=dict)  # count -> frequency
    total_wins: int = 0
    total_appearances: int = 0  # across all reel/row positions

    @property
    def win_rate(self) -> float:
        """Fraction of spin appearances that resulted in any win."""
        if self.total_appearances == 0:
            return 0.0
        return self.total_wins / self.total_appearances


@dataclass
class WinReport:
    """Complete win-statistics report."""

    total_spins: int
    rtp_observed: float  # total_win / (total_spins * bet_amount)
    symbol_summaries: list[SymbolWinSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spins": self.total_spins,
            "rtp_observed": round(self.rtp_observed, 4),
            "symbols": [
                {
                    "symbol": s.symbol,
                    "total_wins": s.total_wins,
                    "total_appearances": s.total_appearances,
                    "win_rate": round(s.win_rate, 6),
                    "wins_by_count": {str(k): v for k, v in sorted(s.wins_by_count.items())},
                }
                for s in sorted(
                    self.symbol_summaries, key=lambda x: x.total_wins, reverse=True
                )
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def print_table(self) -> None:
        """Print a formatted table to stdout."""
        print(f"\n{'='*70}")
        print(f"  Win Statistics  (total spins: {self.total_spins:,})")
        print(f"  Observed RTP: {self.rtp_observed:.2%}")
        print(f"{'='*70}")
        header = f"{'Symbol':<20} {'Total Wins':>11} {'Appearances':>12} {'Win Rate':>10}"
        count_headers = "   2x    3x    4x    5x"
        print(header + count_headers)
        print("-" * 80)
        for s in sorted(self.symbol_summaries, key=lambda x: x.total_wins, reverse=True):
            counts = "".join(f"{s.wins_by_count.get(c, 0):>6}" for c in [2, 3, 4, 5])
            print(
                f"{s.symbol:<20} {s.total_wins:>11,} {s.total_appearances:>12,} "
                f"{s.win_rate:>9.4%}{counts}"
            )
        print("=" * 70)


class WinStatsAnalyser:
    """Produces a :class:`WinReport` from accumulated :class:`GameStats`."""

    def analyse(self, stats: GameStats, bet_amount: float = 1.0) -> WinReport:
        """Build and return a :class:`WinReport`.

        Args:
            stats:      Accumulated game statistics.
            bet_amount: Bet amount per spin used to calculate RTP.
        """
        summaries: dict[str, SymbolWinSummary] = {}

        # Win frequencies
        for symbol, cnt_map in stats.win_frequency.items():
            summary = summaries.setdefault(symbol, SymbolWinSummary(symbol=symbol))
            for cnt, freq in cnt_map.items():
                summary.wins_by_count[cnt] = summary.wins_by_count.get(cnt, 0) + freq
                summary.total_wins += freq

        # Total appearances per symbol (summed over all reel/row positions)
        for _reel, row_map in stats.symbol_position_counts.items():
            for _row, sym_map in row_map.items():
                for symbol, count in sym_map.items():
                    summary = summaries.setdefault(symbol, SymbolWinSummary(symbol=symbol))
                    summary.total_appearances += count

        total_bet = stats.total_spins * bet_amount
        rtp = stats.total_win_amount / total_bet if total_bet > 0 else 0.0

        return WinReport(
            total_spins=stats.total_spins,
            rtp_observed=rtp,
            symbol_summaries=list(summaries.values()),
        )
