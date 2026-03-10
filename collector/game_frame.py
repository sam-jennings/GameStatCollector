"""Interaction with the game iframe on slotstemple.com.

The game is rendered inside an ``<iframe>`` element.  This module locates
the iframe, waits for the game to load, and provides methods to trigger
spins and read the current state.

Since many slot games render to a ``<canvas>`` element (no accessible DOM
symbols), spin detection relies primarily on the :class:`NetworkExtractor`
listening for API responses on the browser context level.  The methods here
handle browser-level interaction only.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Ordered list of CSS selectors tried to locate the spin button.
_SPIN_BUTTON_SELECTORS = [
    "[data-role='spin']",
    "[data-testid='spin-button']",
    "button[aria-label*='spin' i]",
    "button[aria-label*='Spin' i]",
    "[class*='spinButton']",
    "[class*='spin-button']",
    "[class*='btn-spin']",
    "[id*='spin']",
    # Generic canvas fallback – many games use a single canvas; clicking the
    # bottom-centre is where the spin button typically lives.
    "canvas",
]

# Selectors for "loading" indicators that should disappear before the game
# is considered ready.
_LOADING_SELECTORS = [
    "[class*='loading']",
    "[class*='preload']",
    "[id*='loading']",
]


class GameFrame:
    """Controls the slot game running inside *frame*.

    Args:
        frame: A Playwright :class:`Frame` pointing at the game iframe.
    """

    def __init__(self, frame: Any) -> None:
        self._frame = frame
        self._spin_selector: str | None = None  # cached working selector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait_for_game_ready(self, timeout_ms: int = 30_000) -> None:
        """Block until the game loading overlay disappears."""
        for selector in _LOADING_SELECTORS:
            try:
                locator = self._frame.locator(selector)
                if locator.count():
                    locator.wait_for(state="hidden", timeout=timeout_ms)
                    logger.debug("Loading overlay hidden (%s)", selector)
                    return
            except Exception:
                pass
        # No loading indicator found – assume ready.
        time.sleep(1)

    def spin(self) -> bool:
        """Click the spin button.  Returns *True* on success."""
        # Try the cached selector first.
        if self._spin_selector:
            if self._click_selector(self._spin_selector):
                return True
            self._spin_selector = None  # cached selector no longer works

        for selector in _SPIN_BUTTON_SELECTORS:
            if self._click_selector(selector):
                self._spin_selector = selector
                return True

        # Keyboard fallback: Space and Enter trigger spin in many games.
        for key in ("Space", "Enter"):
            try:
                self._frame.page.keyboard.press(key)
                logger.debug("Spin via keyboard %s", key)
                return True
            except Exception:
                pass

        logger.warning("Could not find a spin button to click")
        return False

    def wait_for_spin_complete(self, timeout_ms: int = 15_000) -> None:
        """Wait for the spin animation to finish.

        Strategy: after a spin we expect the page to become idle
        (network requests settle).  We simply wait a fixed short interval as
        an approximation; real implementations might poll an in-game idle
        indicator.
        """
        # Allow animation time – minimum 3 s, configurable.
        pause = max(timeout_ms / 1000, 3)
        time.sleep(pause)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _click_selector(self, selector: str) -> bool:
        try:
            locator = self._frame.locator(selector).first
            if locator.count() == 0:
                return False
            if selector == "canvas":
                # Click bottom-centre of canvas where spin button lives.
                bbox = locator.bounding_box()
                if not bbox:
                    return False
                locator.scroll_into_view_if_needed(timeout=2_000)
                locator.click(
                    position={
                        "x": bbox["width"] / 2,
                        "y": bbox["height"] * 0.85,
                    },
                    timeout=3_000,
                    force=True,
                )
                logger.debug(
                    "Clicked canvas at relative position (%.0f, %.0f)",
                    bbox["width"] / 2,
                    bbox["height"] * 0.85,
                )
                return True
            locator.click(timeout=3_000)
            logger.debug("Clicked spin button via selector %r", selector)
            return True
        except Exception as exc:
            logger.debug("Click failed for selector %r: %s", selector, exc)
            return False
