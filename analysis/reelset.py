"""Reelset reconstruction from observed spin data.

Strategy
--------
A physical reel strip is a *circular sequence* of symbols.  On each spin,
the reel stops at a uniformly-random position, showing ``num_rows`` consecutive
symbols through the game window.

Given many observed ``(reel, row, symbol)`` triples we can:

1. Estimate the **weight** (frequency) of each symbol on each reel.
2. Attempt to **reconstruct the actual strip order** using a greedy graph
   walk over observed consecutive-symbol pairs.

Reconstruction accuracy improves with more spins.  The theoretical minimum is
roughly ``strip_length * num_rows`` spins per reel, but practically several
thousand spins are needed for high confidence.

Output
------
* Per-reel **symbol weights** (normalised to strip length).
* A candidate **reel strip** (ordered symbol list) for each reel.
* A **confidence score** per reel (0–1) based on how well the observed
  transition frequencies match the reconstructed strip.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from collector.models import GameStats

logger = logging.getLogger(__name__)

_DEFAULT_STRIP_LENGTH = 40  # assumed number of stops on a reel strip


@dataclass
class ReelReconstruction:
    """Reconstruction result for a single reel."""

    reel_index: int
    strip: list[str]  # inferred symbol order
    symbol_weights: dict[str, float]  # symbol -> relative weight (sums to 1.0)
    symbol_counts: dict[str, int]  # raw occurrence counts
    confidence: float  # 0.0–1.0


@dataclass
class ReelsetReport:
    """Complete reelset reconstruction report."""

    total_spins: int
    reels: list[ReelReconstruction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spins": self.total_spins,
            "reels": [
                {
                    "reel_index": r.reel_index,
                    "strip": r.strip,
                    "symbol_weights": {k: round(v, 6) for k, v in r.symbol_weights.items()},
                    "symbol_counts": r.symbol_counts,
                    "confidence": round(r.confidence, 4),
                }
                for r in self.reels
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def print_summary(self) -> None:
        print(f"\n{'='*60}")
        print(f"  Reelset Reconstruction  (total spins: {self.total_spins:,})")
        print(f"{'='*60}")
        for reel in self.reels:
            print(f"\n  Reel {reel.reel_index + 1}  (confidence: {reel.confidence:.1%})")
            print(f"  {'Symbol':<20} {'Weight':>8}  {'Count':>8}")
            print("  " + "-" * 40)
            for sym, weight in sorted(
                reel.symbol_weights.items(), key=lambda x: x[1], reverse=True
            ):
                count = reel.symbol_counts.get(sym, 0)
                print(f"  {sym:<20} {weight:>8.4f}  {count:>8,}")
            if reel.strip:
                strip_preview = " → ".join(reel.strip[:10])
                if len(reel.strip) > 10:
                    strip_preview += " → …"
                print(f"\n  Strip preview: {strip_preview}")
        print("=" * 60)


class ReelsetReconstructor:
    """Reconstructs reel strips from :class:`GameStats`.

    Usage::

        reconstructor = ReelsetReconstructor()
        report = reconstructor.reconstruct(stats, num_rows=3)
        report.print_summary()
    """

    def reconstruct(
        self,
        stats: GameStats,
        num_rows: int = 3,
        strip_length: int = _DEFAULT_STRIP_LENGTH,
    ) -> ReelsetReport:
        """Build a :class:`ReelsetReport` from accumulated statistics.

        Args:
            stats:        Accumulated :class:`~collector.models.GameStats`.
            num_rows:     Number of visible rows in the game window.
            strip_length: Assumed reel-strip length (number of stops).
        """
        reels: list[ReelReconstruction] = []

        for reel_idx in sorted(stats.symbol_position_counts):
            row_map = stats.symbol_position_counts[reel_idx]

            # Aggregate symbol counts across all rows of this reel.
            total_counts: Counter[str] = Counter()
            for row_map_entry in row_map.values():
                total_counts.update(row_map_entry)

            if not total_counts:
                continue

            total_obs = sum(total_counts.values())
            symbol_weights = {
                sym: count / total_obs for sym, count in total_counts.items()
            }

            # Build candidate strip via greedy transition-graph walk.
            sequences = stats.reel_sequences.get(reel_idx, [])
            strip = self._reconstruct_strip(sequences, strip_length)
            confidence = self._compute_confidence(strip, sequences, num_rows)

            reels.append(
                ReelReconstruction(
                    reel_index=reel_idx,
                    strip=strip,
                    symbol_weights=symbol_weights,
                    symbol_counts=dict(total_counts),
                    confidence=confidence,
                )
            )

        return ReelsetReport(total_spins=stats.total_spins, reels=reels)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reconstruct_strip(
        sequences: list[str],
        strip_length: int,
    ) -> list[str]:
        """Build a candidate strip via greedy walk on the transition graph.

        The transition graph records how often symbol *A* is immediately
        followed by symbol *B* in the observed middle-row sequence.  A greedy
        walk from the most-frequent starting symbol produces a candidate strip.
        """
        if not sequences:
            return []

        # Build bigram transition counts.
        transitions: dict[str, Counter[str]] = {}
        for i in range(len(sequences) - 1):
            src, dst = sequences[i], sequences[i + 1]
            if src not in transitions:
                transitions[src] = Counter()
            transitions[src][dst] += 1

        if not transitions:
            return []

        # Start from the most common symbol.
        start = Counter(sequences).most_common(1)[0][0]
        strip: list[str] = [start]
        visited_transitions: dict[str, dict[str, int]] = {
            k: dict(v) for k, v in transitions.items()
        }

        for _ in range(strip_length - 1):
            current = strip[-1]
            candidates = visited_transitions.get(current)
            if not candidates:
                break
            # Pick the most likely next symbol.
            nxt = max(candidates, key=lambda s: candidates[s])
            strip.append(nxt)
            candidates[nxt] -= 1
            if candidates[nxt] <= 0:
                del candidates[nxt]

        return strip

    @staticmethod
    def _compute_confidence(
        strip: list[str],
        sequences: list[str],
        num_rows: int,
    ) -> float:
        """Score how well *strip* explains the observed *sequences*.

        Confidence is the fraction of observed bigrams that are present in the
        reconstructed strip (considering its circular nature).
        """
        if not strip or not sequences or len(sequences) < 2:
            return 0.0

        # Build a set of bigrams in the strip (circular).
        strip_bigrams: set[tuple[str, str]] = set()
        n = len(strip)
        for i in range(n):
            strip_bigrams.add((strip[i], strip[(i + 1) % n]))

        matched = sum(
            1
            for i in range(len(sequences) - 1)
            if (sequences[i], sequences[i + 1]) in strip_bigrams
        )
        total = len(sequences) - 1
        return matched / total if total > 0 else 0.0
