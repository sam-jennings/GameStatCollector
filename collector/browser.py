"""Browser setup and the slotstemple.com page wrapper.

This module:
* Launches a Playwright browser (Chromium, headed or headless).
* Navigates to the target page and handles consent popups.
* Locates the game ``<iframe>`` and returns a handle to it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# URL of the target game.
GAME_URL = "https://www.slotstemple.com/us/free-slots/mystic-fortune"

# Ordered selectors for dismissing cookie/GDPR consent dialogs.
_CONSENT_SELECTORS = [
    "button[id*='accept' i]",
    "button[aria-label*='accept' i]",
    "button[class*='accept' i]",
    "button[class*='agree' i]",
    "[data-role='accept']",
]

# Selectors tried to locate the game iframe.
_IFRAME_SELECTORS = [
    "iframe[src*='habanero']",
    "iframe[src*='slot']",
    "iframe[src*='game']",
    "iframe[id*='game']",
    "iframe[class*='game']",
    "iframe",  # last-resort: first iframe on page
]

# A "Play" or "Launch" button that some aggregator sites show before the
# iframe becomes interactive.
_PLAY_BUTTON_SELECTORS = [
    "button[aria-label*='play' i]",
    "button[class*='play' i]",
    "[data-role='play']",
    "[id*='play-button']",
]


def launch_browser(playwright: Any, headless: bool = False) -> Any:
    """Launch and return a Chromium browser instance.

    Args:
        playwright: An active :class:`playwright.sync_api.Playwright` instance.
        headless:   Run browser without a visible window when *True*.
    """
    return playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )


def open_game_page(
    browser: Any,
    network_extractor: Any,
    url: str = GAME_URL,
    timeout_ms: int = 30_000,
) -> tuple[Any, Any]:
    """Open the game page and return ``(page, game_frame)``.

    Args:
        browser:           Playwright browser instance.
        network_extractor: :class:`~collector.network_extractor.NetworkExtractor`
                           instance; its :meth:`attach` method will be called on
                           the new browser context so that responses from inside
                           the game iframe are also captured.
        url:               Full URL of the game page.
        timeout_ms:        Page load timeout in milliseconds.

    Returns:
        ``(page, frame)`` where *frame* is the Playwright :class:`Frame`
        representing the game iframe (or the page's main frame if no iframe is
        found).
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    # Attach network extractor BEFORE any navigation so nothing is missed.
    network_extractor.attach(context)

    page = context.new_page()
    logger.info("Navigating to %s", url)
    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=timeout_ms)

    _dismiss_consent(page)
    _click_play_button(page)

    frame = _find_game_frame(page, timeout_ms)
    return page, frame


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _dismiss_consent(page: Any) -> None:
    """Click consent/cookie accept buttons if present."""
    for selector in _CONSENT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2_000):
                btn.click()
                logger.debug("Dismissed consent dialog via %r", selector)
                time.sleep(0.5)
                return
        except Exception:
            pass


def _click_play_button(page: Any) -> None:
    """Click a 'Play' overlay button if one is shown."""
    for selector in _PLAY_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2_000):
                btn.click()
                logger.debug("Clicked play button via %r", selector)
                time.sleep(1)
                return
        except Exception:
            pass


def _find_game_frame(page: Any, timeout_ms: int) -> Any:
    """Return the game iframe :class:`Frame`, or the page's main frame."""
    for selector in _IFRAME_SELECTORS:
        try:
            iframe_el = page.locator(selector).first
            if iframe_el.count() == 0:
                continue
            iframe_el.wait_for(state="attached", timeout=timeout_ms)
            frame = iframe_el.content_frame()
            if frame:
                logger.info("Found game frame via selector %r: %s", selector, frame.url)
                return frame
        except Exception as exc:
            logger.debug("Iframe selector %r failed: %s", selector, exc)

    logger.warning("No game iframe found; using main page frame")
    return page.main_frame
