"""Main collector loop.

Orchestrates the browser, network extractor, game interaction, and data
storage to run ``num_spins`` automated spins and persist the results.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from collector.browser import launch_browser, open_game_page
from collector.dom_extractor import DomExtractor
from collector.game_frame import GameFrame
from collector.models import ReelState, SpinResult, Win
from collector.network_extractor import NetworkExtractor
from collector.response_parser import parse_spin
from collector.stats import StatsTracker
from collector.storage import DataStore

logger = logging.getLogger(__name__)

_DEFAULT_BET = 1.0
_SPIN_WAIT_SECONDS = 5  # seconds to wait for spin animation to settle


class Collector:
    """Runs the automated spin loop.

    Args:
        data_dir:        Directory for storing collected data.
        headless:        Run the browser headlessly.
        bet_amount:      Bet amount per spin (used for RTP calculation).
        spin_timeout_ms: Maximum time to wait for one spin to complete.
    """

    def __init__(
        self,
        data_dir: Path | str = "data",
        headless: bool = False,
        bet_amount: float = _DEFAULT_BET,
        spin_timeout_ms: int = 15_000,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._headless = headless
        self._bet_amount = bet_amount
        self._spin_timeout_ms = spin_timeout_ms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, num_spins: int = 100) -> StatsTracker:
        """Run *num_spins* automated spins and return the accumulated stats.

        Args:
            num_spins: Number of spins to perform.

        Returns:
            A :class:`~collector.stats.StatsTracker` with the accumulated
            statistics (also saved to *data_dir*).
        """
        from playwright.sync_api import sync_playwright

        store = DataStore(self._data_dir)
        tracker = self._load_or_create_tracker()
        spin_id_start = store.count_spins()

        extractor = NetworkExtractor()

        with sync_playwright() as pw:
            browser = launch_browser(pw, headless=self._headless)
            try:
                page, frame = open_game_page(browser, extractor)
                game = GameFrame(frame)
                dom = DomExtractor(frame)

                game.wait_for_game_ready()
                logger.info("Game ready.  Starting %d spins …", num_spins)

                for i in range(num_spins):
                    spin_id = spin_id_start + i
                    logger.info("Spin %d / %d", i + 1, num_spins)
                    extractor.clear()

                    spun = game.spin()
                    if not spun:
                        logger.error("Could not trigger spin – aborting")
                        break

                    time.sleep(_SPIN_WAIT_SECONDS)

                    spin_result = self._extract_spin_result(
                        extractor, dom, spin_id, page
                    )
                    if spin_result:
                        store.append_spin(spin_result)
                        tracker.record(spin_result)
                        logger.info(
                            "  → win: %.2f  |  symbols: %s",
                            spin_result.total_win,
                            spin_result.reel_state.symbols,
                        )
                    else:
                        logger.warning("  → no parseable result for spin %d", spin_id)

                    # Save stats after every spin so progress isn't lost.
                    tracker.save(self._data_dir / "stats.json")

            finally:
                browser.close()

        return tracker

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_or_create_tracker(self) -> StatsTracker:
        stats_path = self._data_dir / "stats.json"
        if stats_path.exists():
            logger.info("Resuming from existing stats at %s", stats_path)
            return StatsTracker.load(stats_path)
        return StatsTracker()

    def _extract_spin_result(
        self,
        extractor: NetworkExtractor,
        dom: DomExtractor,
        spin_id: int,
        page: Any,
    ) -> SpinResult | None:
        # 1. Try network interception (most reliable).
        raw = extractor.pop_latest_spin()
        if raw:
            result = parse_spin(raw["body"], spin_id, self._bet_amount)
            if result:
                return result
            logger.debug("Network payload found but not parseable; storing raw")
            DataStore(self._data_dir).append_raw_response(raw)

        # 2. DOM fallback.
        symbols = dom.read_visible_symbols()
        win_amount = dom.read_win_amount() or 0.0
        if symbols:
            logger.debug("Extracted symbols from DOM")
            return SpinResult.create(
                spin_id=spin_id,
                reel_state=ReelState(symbols=symbols),
                wins=[],  # wins not parseable from DOM alone
                total_win=win_amount,
                bet_amount=self._bet_amount,
            )

        return None
