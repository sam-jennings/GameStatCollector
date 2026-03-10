"""Statistics tracker: accumulates GameStats from individual SpinResults."""

from __future__ import annotations

import json
from pathlib import Path

from collector.models import GameStats, SpinResult


class StatsTracker:
    """Incrementally builds :class:`GameStats` from :class:`SpinResult` objects.

    Usage::

        tracker = StatsTracker()
        tracker.record(spin_result)
        stats = tracker.stats
    """

    def __init__(self, stats: GameStats | None = None) -> None:
        self.stats: GameStats = stats or GameStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, spin: SpinResult) -> None:
        """Incorporate a single spin result into the running statistics."""
        s = self.stats
        s.total_spins += 1
        s.total_win_amount += spin.total_win

        self._record_symbol_positions(spin)
        self._record_wins(spin)

    def save(self, path: Path | str) -> None:
        """Persist the current statistics to *path* as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.stats.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> StatsTracker:
        """Load previously saved statistics from *path*."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(stats=GameStats.from_dict(data))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_symbol_positions(self, spin: SpinResult) -> None:
        s = self.stats
        for reel_idx, reel_symbols in enumerate(spin.reel_state.symbols):
            reel_counts = s.symbol_position_counts.setdefault(reel_idx, {})
            for row_idx, symbol in enumerate(reel_symbols):
                row_counts = reel_counts.setdefault(row_idx, {})
                row_counts[symbol] = row_counts.get(symbol, 0) + 1

            # Record middle-row symbol for reel-sequence tracking.
            middle_row = len(reel_symbols) // 2
            seq = s.reel_sequences.setdefault(reel_idx, [])
            seq.append(reel_symbols[middle_row])

    def _record_wins(self, spin: SpinResult) -> None:
        s = self.stats
        for win in spin.wins:
            sym_map = s.win_frequency.setdefault(win.symbol, {})
            sym_map[win.count] = sym_map.get(win.count, 0) + 1
