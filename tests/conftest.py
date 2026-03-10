"""Shared pytest fixtures for GameStatCollector tests."""

from __future__ import annotations

import pytest

from collector.models import ReelState, SpinResult, Win


def make_spin(
    spin_id: int,
    symbols: list[list[str]],
    wins: list[Win] | None = None,
    total_win: float = 0.0,
    bet_amount: float = 1.0,
) -> SpinResult:
    """Build a :class:`SpinResult` for use in tests."""
    return SpinResult.create(
        spin_id=spin_id,
        reel_state=ReelState(symbols=symbols),
        wins=wins or [],
        total_win=total_win,
        bet_amount=bet_amount,
    )
