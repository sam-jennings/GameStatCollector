"""DOM-based data extraction fallback.

When the game renders everything to a ``<canvas>`` element, DOM-based
extraction cannot read individual symbols.  However, many games expose:

* A visible credit/win-amount text element that changes after each spin.
* Accessibility (ARIA) labels or ``data-*`` attributes on symbol nodes.

This module attempts to read whatever is available in the iframe's DOM and
returns a best-effort partial :class:`~collector.models.SpinResult`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# CSS selectors tried in order to locate the "total win" display.
_WIN_AMOUNT_SELECTORS = [
    "[data-role='win-amount']",
    "[class*='win'][class*='amount']",
    "[class*='winAmount']",
    "[class*='win-amount']",
    "[id*='win']",
    "[class*='totalwin']",
    "[class*='total-win']",
]

# CSS selectors tried in order to locate individual symbol elements.
_SYMBOL_SELECTORS = [
    "[data-symbol]",
    "[data-role='symbol']",
    "[class*='symbol']",
    "[aria-label]",
]


class DomExtractor:
    """Reads game-state information from the game's iframe DOM.

    Usage::

        extractor = DomExtractor(frame)
        win_amount = extractor.read_win_amount()
        symbols    = extractor.read_visible_symbols()
    """

    def __init__(self, frame: Any) -> None:
        """
        Args:
            frame: A Playwright :class:`Frame` pointing at the game iframe.
        """
        self._frame = frame

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_win_amount(self) -> float | None:
        """Return the displayed win amount, or *None* if not readable."""
        for selector in _WIN_AMOUNT_SELECTORS:
            try:
                el = self._frame.locator(selector).first
                if el.count() == 0:
                    continue
                text = el.inner_text(timeout=500)
                amount = _parse_number(text)
                if amount is not None:
                    logger.debug("Win amount from selector %r: %s", selector, amount)
                    return amount
            except Exception:
                pass
        return None

    def read_visible_symbols(self) -> list[list[str]] | None:
        """Return ``symbols[reel][row]`` read from the DOM, or *None*.

        Returns *None* when no symbol elements are found (e.g. canvas game).
        """
        for selector in _SYMBOL_SELECTORS:
            try:
                elements = self._frame.locator(selector).all()
                if not elements:
                    continue
                labels = self._extract_labels(elements)
                if labels:
                    grid = self._labels_to_grid(labels)
                    if grid:
                        logger.debug(
                            "Read %d symbol elements via selector %r",
                            len(labels),
                            selector,
                        )
                        return grid
            except Exception:
                pass
        return None

    def read_raw_dom_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of DOM properties useful for debugging."""
        snapshot: dict[str, Any] = {}
        try:
            snapshot["title"] = self._frame.title()
        except Exception:
            pass
        try:
            snapshot["url"] = self._frame.url
        except Exception:
            pass
        for selector in _WIN_AMOUNT_SELECTORS + _SYMBOL_SELECTORS:
            try:
                count = self._frame.locator(selector).count()
                if count:
                    snapshot[selector] = count
            except Exception:
                pass
        return snapshot

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_labels(elements: list[Any]) -> list[str]:
        labels: list[str] = []
        for el in elements:
            try:
                label = (
                    el.get_attribute("data-symbol")
                    or el.get_attribute("aria-label")
                    or el.get_attribute("data-name")
                    or el.inner_text(timeout=200).strip()
                )
                if label:
                    labels.append(label.strip())
            except Exception:
                pass
        return labels

    @staticmethod
    def _labels_to_grid(labels: list[str]) -> list[list[str]] | None:
        """Attempt to arrange a flat list of labels into a reel × row grid.

        Assumes the most common 5-reel × 3-row layout as the default.
        """
        total = len(labels)
        if total == 0:
            return None
        # Try common grid sizes: 5×3, 5×4, 3×3, 6×4
        for num_reels, num_rows in [(5, 3), (5, 4), (3, 3), (6, 4), (3, 5)]:
            if total == num_reels * num_rows:
                grid = [
                    labels[r * num_rows: (r + 1) * num_rows]
                    for r in range(num_reels)
                ]
                return grid
        # Fallback: single column
        return [labels]


def _parse_number(text: str) -> float | None:
    """Extract the first numeric value from *text*."""
    text = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None
