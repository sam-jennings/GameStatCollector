"""GameStatCollector – entry point.

Usage
-----
Collect 200 spins (visible browser window)::

    python main.py collect --spins 200

Collect headlessly::

    python main.py collect --spins 500 --headless

Analyse previously collected data::

    python main.py analyse

Show reelset reconstruction::

    python main.py reelset
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

DATA_DIR = Path("data")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> None:
    """Run the automated spin collector."""
    from collector.collector import Collector

    collector = Collector(
        data_dir=DATA_DIR,
        headless=args.headless,
        bet_amount=args.bet,
    )
    logger.info("Starting collection: %d spin(s), headless=%s", args.spins, args.headless)
    tracker = collector.run(num_spins=args.spins)
    logger.info(
        "Done.  Recorded %d spins, total win %.2f",
        tracker.stats.total_spins,
        tracker.stats.total_win_amount,
    )


def cmd_analyse(args: argparse.Namespace) -> None:
    """Print win-statistics analysis of collected data."""
    from analysis.win_stats import WinStatsAnalyser
    from collector.stats import StatsTracker

    stats_path = DATA_DIR / "stats.json"
    if not stats_path.exists():
        sys.exit(f"No stats file found at {stats_path}. Run 'collect' first.")

    tracker = StatsTracker.load(stats_path)
    analyser = WinStatsAnalyser()
    report = analyser.analyse(tracker.stats, bet_amount=args.bet)
    report.print_table()

    out_path = DATA_DIR / "win_stats_report.json"
    out_path.write_text(report.to_json(), encoding="utf-8")
    logger.info("Win stats report saved to %s", out_path)


def cmd_reelset(args: argparse.Namespace) -> None:
    """Print reelset reconstruction from collected data."""
    from analysis.reelset import ReelsetReconstructor
    from collector.stats import StatsTracker

    stats_path = DATA_DIR / "stats.json"
    if not stats_path.exists():
        sys.exit(f"No stats file found at {stats_path}. Run 'collect' first.")

    tracker = StatsTracker.load(stats_path)
    reconstructor = ReelsetReconstructor()
    report = reconstructor.reconstruct(tracker.stats, num_rows=args.rows)
    report.print_summary()

    out_path = DATA_DIR / "reelset_report.json"
    out_path.write_text(report.to_json(), encoding="utf-8")
    logger.info("Reelset report saved to %s", out_path)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="GameStatCollector – automated slot game stat collector",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # collect
    p_collect = sub.add_parser("collect", help="Run automated spins and collect data")
    p_collect.add_argument(
        "--spins", type=int, default=100, help="Number of spins to run (default: 100)"
    )
    p_collect.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    p_collect.add_argument(
        "--bet", type=float, default=1.0, help="Bet amount per spin (default: 1.0)"
    )

    # analyse
    p_analyse = sub.add_parser("analyse", help="Analyse collected win statistics")
    p_analyse.add_argument(
        "--bet", type=float, default=1.0, help="Bet amount per spin (default: 1.0)"
    )

    # reelset
    p_reelset = sub.add_parser("reelset", help="Reconstruct reelsets from collected data")
    p_reelset.add_argument(
        "--rows", type=int, default=3, help="Number of visible rows (default: 3)"
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "analyse":
        cmd_analyse(args)
    elif args.command == "reelset":
        cmd_reelset(args)
    else:
        parser.print_help()
        sys.exit(1)
