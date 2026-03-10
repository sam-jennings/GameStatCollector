"""Persistent storage for spin results and statistics.

Spin results are appended to a newline-delimited JSON (NDJSON) file so that
large data sets can be read incrementally without loading the entire file into
memory.  Statistics are saved as a single JSON object.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from collector.models import SpinResult

logger = logging.getLogger(__name__)

_SPINS_FILENAME = "spins.ndjson"
_STATS_FILENAME = "stats.json"
_RAW_RESPONSES_FILENAME = "raw_responses.ndjson"


class DataStore:
    """Reads and writes collected game data to *data_dir*.

    Args:
        data_dir: Directory where all data files are stored.
    """

    def __init__(self, data_dir: Path | str = "data") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._spins_path = self._dir / _SPINS_FILENAME
        self._raw_path = self._dir / _RAW_RESPONSES_FILENAME

    # ------------------------------------------------------------------
    # Spin results
    # ------------------------------------------------------------------

    def append_spin(self, spin: SpinResult) -> None:
        """Append *spin* to the NDJSON spins file."""
        with self._spins_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(spin.to_dict()) + "\n")

    def load_spins(self) -> list[SpinResult]:
        """Load all previously saved spin results."""
        if not self._spins_path.exists():
            return []
        results: list[SpinResult] = []
        with self._spins_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        results.append(SpinResult.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.warning("Skipping malformed spin record: %s", exc)
        return results

    def count_spins(self) -> int:
        """Return the number of saved spin records without loading them."""
        if not self._spins_path.exists():
            return 0
        count = 0
        with self._spins_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    count += 1
        return count

    # ------------------------------------------------------------------
    # Raw API responses (for debugging / re-parsing)
    # ------------------------------------------------------------------

    def append_raw_response(self, response: dict) -> None:
        """Save a raw network response payload."""
        with self._raw_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(response) + "\n")
