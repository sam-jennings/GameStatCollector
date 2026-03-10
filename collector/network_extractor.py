"""Network response interception for game API calls.

Playwright context-level response listeners capture every HTTP response,
including those from inside iframes.  This module examines each response,
identifies likely spin-result payloads, and stores them for later parsing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Keywords that often appear in slot-game spin-result JSON payloads.
_SPIN_KEYWORDS = frozenset(
    [
        "reels",
        "symbols",
        "winlines",
        "win_lines",
        "paylines",
        "stops",
        "positions",
        "spinresult",
        "spin_result",
        "gameresult",
        "game_result",
        "scatterwin",
        "freespins",
        "multiplier",
    ]
)


class NetworkExtractor:
    """Attaches to a Playwright :class:`BrowserContext` and collects spin data.

    Usage::

        extractor = NetworkExtractor()
        extractor.attach(context)          # start listening
        # … trigger a spin in the browser …
        raw = extractor.pop_latest_spin()  # retrieve captured payload
        extractor.clear()                  # reset for next spin
    """

    def __init__(self) -> None:
        self._all_responses: list[dict[str, Any]] = []
        self._spin_responses: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def attach(self, context: Any) -> None:
        """Register response listener on *context* (a Playwright BrowserContext)."""
        context.on("response", self._on_response)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_response(self, response: Any) -> None:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and "javascript" not in content_type:
            return
        try:
            body = response.json()
        except Exception:
            return

        entry = {"url": response.url, "status": response.status, "body": body}
        self._all_responses.append(entry)

        if self._looks_like_spin_result(body):
            logger.debug("Captured spin response from %s", response.url)
            self._spin_responses.append(entry)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def pop_latest_spin(self) -> dict[str, Any] | None:
        """Remove and return the most recently captured spin response, or None."""
        if self._spin_responses:
            return self._spin_responses.pop()
        return None

    def all_spin_responses(self) -> list[dict[str, Any]]:
        """Return a copy of all captured spin responses."""
        return list(self._spin_responses)

    def all_responses(self) -> list[dict[str, Any]]:
        """Return a copy of every captured JSON response (for debugging)."""
        return list(self._all_responses)

    def clear(self) -> None:
        """Discard all captured responses."""
        self._all_responses.clear()
        self._spin_responses.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_spin_result(body: Any) -> bool:
        """Heuristic: check whether *body* looks like a spin-result payload."""
        try:
            body_str = json.dumps(body).lower()
        except (TypeError, ValueError):
            return False
        return any(kw in body_str for kw in _SPIN_KEYWORDS)
