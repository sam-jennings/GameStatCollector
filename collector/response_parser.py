"""Parses raw API response payloads captured by :class:`NetworkExtractor`.

Different game providers use different JSON shapes.  This module applies a
chain of parsers and returns the first successful result.

Supported provider formats
--------------------------
* **Habanero** – reels field is a list-of-lists; wins contain ``lineWin``
  objects with ``symbolId``, ``symbolCount``, ``positions``.
* **Generic** – best-effort extraction from any JSON containing the keywords
  ``reels``/``symbols`` and ``wins``/``winlines``.

If none of the structured parsers recognise the payload, ``parse_spin``
returns ``None`` and the caller can store the raw payload for later manual
analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from collector.models import ReelState, SpinResult, Win

logger = logging.getLogger(__name__)


def parse_spin(
    raw: dict[str, Any],
    spin_id: int,
    bet_amount: float,
) -> SpinResult | None:
    """Attempt to parse *raw* as a spin result.

    Tries each registered parser in turn; returns the first successful
    :class:`SpinResult` or *None* if no parser succeeds.
    """
    for parser in (_parse_habanero, _parse_generic):
        try:
            result = parser(raw, spin_id, bet_amount)
            if result is not None:
                return result
        except Exception as exc:
            logger.debug("Parser %s failed: %s", parser.__name__, exc)
    logger.warning("No parser recognised the spin payload from URL context")
    return None


# ---------------------------------------------------------------------------
# Habanero parser
# ---------------------------------------------------------------------------

def _parse_habanero(
    raw: dict[str, Any],
    spin_id: int,
    bet_amount: float,
) -> SpinResult | None:
    """Parse a Habanero-style spin response.

    Expected shape (simplified)::

        {
          "data": {
            "reels": [[sym, …], …],   # list of reels, each a list of symbol IDs
            "winLines": [
              {
                "lineIndex": 0,
                "symbolId": "WILD",
                "symbolCount": 3,
                "positions": [[reel, row], …],
                "lineWin": 2.5
              },
              …
            ],
            "totalWin": 5.0
          }
        }
    """
    data = raw.get("data") or raw
    # Require at least one Habanero-specific key to avoid false matches.
    if not any(k in data for k in ("winLines", "win_lines", "totalWin", "reelSymbols")):
        return None

    reels_raw = data.get("reels") or data.get("reel") or data.get("reelSymbols")
    if not reels_raw or not isinstance(reels_raw, list):
        return None

    # Normalise reels to list[list[str]]
    reels: list[list[str]] = []
    for reel in reels_raw:
        if isinstance(reel, list):
            reels.append([str(sym) for sym in reel])
        else:
            return None

    wins: list[Win] = []
    win_lines = (
        data.get("winLines")
        or data.get("win_lines")
        or data.get("winlines")
        or []
    )
    for wl in win_lines:
        positions = wl.get("positions", [])
        win_reels = [p[0] for p in positions if isinstance(p, (list, tuple))]
        win_rows = [p[1] for p in positions if isinstance(p, (list, tuple))]
        wins.append(
            Win(
                symbol=str(wl.get("symbolId") or wl.get("symbol") or ""),
                count=int(wl.get("symbolCount") or wl.get("count") or len(win_reels)),
                reels=win_reels,
                rows=win_rows,
                amount=float(wl.get("lineWin") or wl.get("win") or 0),
                line_index=wl.get("lineIndex"),
            )
        )

    total_win = float(data.get("totalWin") or data.get("total_win") or 0)

    return SpinResult.create(
        spin_id=spin_id,
        reel_state=ReelState(symbols=reels),
        wins=wins,
        total_win=total_win,
        bet_amount=bet_amount,
        raw_data=raw,
    )


# ---------------------------------------------------------------------------
# Generic parser
# ---------------------------------------------------------------------------

def _parse_generic(
    raw: dict[str, Any],
    spin_id: int,
    bet_amount: float,
) -> SpinResult | None:
    """Best-effort parser for arbitrary slot-game JSON responses."""

    def _find(obj: Any, *keys: str) -> Any:
        """Recursively search *obj* for the first matching key."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() in keys:
                    return v
                found = _find(v, *keys)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _find(item, *keys)
                if found is not None:
                    return found
        return None

    reels_raw = _find(raw, "reels", "symbols", "grid", "reelresult")
    if not reels_raw or not isinstance(reels_raw, list):
        return None

    # Normalise to list[list[str]]
    reels: list[list[str]] = []
    for item in reels_raw:
        if isinstance(item, list):
            reels.append([str(s) for s in item])
        elif isinstance(item, (str, int)):
            # Flat list: treat as single reel
            reels.append([str(item)])
        else:
            continue

    if not reels:
        return None

    total_win = float(_find(raw, "totalwin", "total_win", "win", "payout") or 0)

    wins_raw = _find(raw, "winlines", "win_lines", "wins", "paylines") or []
    wins: list[Win] = []
    if isinstance(wins_raw, list):
        for wl in wins_raw:
            if not isinstance(wl, dict):
                continue
            sym = str(wl.get("symbol") or wl.get("symbolid") or wl.get("id") or "")
            count = int(wl.get("count") or wl.get("symbolcount") or 0)
            amount = float(wl.get("win") or wl.get("amount") or wl.get("linewin") or 0)
            positions = wl.get("positions") or []
            win_reels = [p[0] for p in positions if isinstance(p, (list, tuple))]
            win_rows = [p[1] for p in positions if isinstance(p, (list, tuple))]
            if sym:
                wins.append(
                    Win(
                        symbol=sym,
                        count=count,
                        reels=win_reels,
                        rows=win_rows,
                        amount=amount,
                        line_index=wl.get("line_index") or wl.get("lineindex"),
                    )
                )

    return SpinResult.create(
        spin_id=spin_id,
        reel_state=ReelState(symbols=reels),
        wins=wins,
        total_win=total_win,
        bet_amount=bet_amount,
        raw_data=raw,
    )
