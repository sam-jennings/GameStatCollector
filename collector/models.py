"""Data models for GameStatCollector."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Win:
    """Represents a single winning combination from a spin."""

    symbol: str
    count: int  # matching-symbol length: 2, 3, 4, or 5
    reels: list[int]  # 0-based reel indices where the winning symbols land
    rows: list[int]  # corresponding row indices for each winning symbol
    amount: float  # credit amount won
    line_index: int | None = None  # payline index, if applicable

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "count": self.count,
            "reels": self.reels,
            "rows": self.rows,
            "amount": self.amount,
            "line_index": self.line_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Win:
        return cls(
            symbol=data["symbol"],
            count=data["count"],
            reels=data["reels"],
            rows=data["rows"],
            amount=data["amount"],
            line_index=data.get("line_index"),
        )


@dataclass
class ReelState:
    """The visible window of symbols shown on all reels after a spin.

    ``symbols[reel_index][row_index]`` is the symbol name string.
    Row 0 is the top row; row ``num_rows - 1`` is the bottom row.
    """

    symbols: list[list[str]]  # symbols[reel][row]

    @property
    def num_reels(self) -> int:
        return len(self.symbols)

    @property
    def num_rows(self) -> int:
        return len(self.symbols[0]) if self.symbols else 0

    def to_dict(self) -> dict[str, Any]:
        return {"symbols": self.symbols}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReelState:
        return cls(symbols=data["symbols"])


@dataclass
class SpinResult:
    """Complete record of a single spin."""

    spin_id: int
    timestamp: str  # ISO-8601 UTC
    reel_state: ReelState
    wins: list[Win]
    total_win: float
    bet_amount: float
    raw_data: dict[str, Any] | None = None  # raw API payload for debugging

    @classmethod
    def create(
        cls,
        spin_id: int,
        reel_state: ReelState,
        wins: list[Win],
        total_win: float,
        bet_amount: float,
        raw_data: dict[str, Any] | None = None,
    ) -> SpinResult:
        return cls(
            spin_id=spin_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reel_state=reel_state,
            wins=wins,
            total_win=total_win,
            bet_amount=bet_amount,
            raw_data=raw_data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spin_id": self.spin_id,
            "timestamp": self.timestamp,
            "reel_state": self.reel_state.to_dict(),
            "wins": [w.to_dict() for w in self.wins],
            "total_win": self.total_win,
            "bet_amount": self.bet_amount,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpinResult:
        return cls(
            spin_id=data["spin_id"],
            timestamp=data["timestamp"],
            reel_state=ReelState.from_dict(data["reel_state"]),
            wins=[Win.from_dict(w) for w in data["wins"]],
            total_win=data["total_win"],
            bet_amount=data["bet_amount"],
            raw_data=data.get("raw_data"),
        )


@dataclass
class GameStats:
    """Cumulative statistics across all collected spins.

    Attributes:
        total_spins:            Number of spins recorded.
        total_win_amount:       Sum of all win amounts.
        win_frequency:          win_frequency[symbol][count] = number of times
                                that symbol produced a win of *count* matching
                                symbols.
        symbol_position_counts: symbol_position_counts[reel][row][symbol] =
                                number of times that symbol appeared at
                                (reel, row).
        reel_sequences:         reel_sequences[reel] is the ordered list of
                                middle-row symbols observed across all spins,
                                used for reelset reconstruction.
    """

    total_spins: int = 0
    total_win_amount: float = 0.0
    win_frequency: dict[str, dict[int, int]] = field(default_factory=dict)
    symbol_position_counts: dict[int, dict[int, dict[str, int]]] = field(
        default_factory=dict
    )
    reel_sequences: dict[int, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spins": self.total_spins,
            "total_win_amount": self.total_win_amount,
            "win_frequency": self.win_frequency,
            "symbol_position_counts": self.symbol_position_counts,
            "reel_sequences": self.reel_sequences,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameStats:
        gs = cls(
            total_spins=data.get("total_spins", 0),
            total_win_amount=data.get("total_win_amount", 0.0),
        )
        gs.win_frequency = {
            sym: {int(cnt): freq for cnt, freq in cnt_map.items()}
            for sym, cnt_map in data.get("win_frequency", {}).items()
        }
        gs.symbol_position_counts = {
            int(reel): {
                int(row): sym_map
                for row, sym_map in row_map.items()
            }
            for reel, row_map in data.get("symbol_position_counts", {}).items()
        }
        gs.reel_sequences = {
            int(reel): seq
            for reel, seq in data.get("reel_sequences", {}).items()
        }
        return gs

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
