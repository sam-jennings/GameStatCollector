# GameStatCollector

Automated stat collector for the **Mystic Fortune** slot demo at
[slotstemple.com](https://www.slotstemple.com/us/free-slots/mystic-fortune).

The tool launches a real browser (via [Playwright](https://playwright.dev/python/)),
plays the game automatically, and captures per-spin data by intercepting the
game server's HTTP responses.  Collected data is analysed to produce:

* **Win-frequency tables** – wins per symbol type and win length (2×, 3×, 4×, 5×)
* **Observed RTP** – return-to-player estimate from collected spins
* **Reelset reconstruction** – a statistical estimate of the symbol order on
  each virtual reel strip

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Collect spins

```bash
# 200 spins with a visible browser window (recommended on first run so you can
# verify the game loads correctly):
python main.py collect --spins 200

# 1 000 spins headlessly:
python main.py collect --spins 1000 --headless

# Specify a custom bet amount for RTP calculations:
python main.py collect --spins 500 --bet 2.0
```

Spin data is appended to `data/spins.ndjson`; statistics are updated in
`data/stats.json` after every spin so progress is never lost.

### 3. Analyse win statistics

```bash
python main.py analyse
```

Prints a table like:

```
======================================================================
  Win Statistics  (total spins: 1,000)
  Observed RTP: 95.23%
======================================================================
Symbol               Total Wins  Appearances   Win Rate   2x    3x    4x    5x
--------------------------------------------------------------------------------
WILD                        142        5000    2.8400%     0   120    18     4
GOLD_COIN                    87        4500    1.9333%     0    75    10     2
...
```

Saves a machine-readable copy to `data/win_stats_report.json`.

### 4. Reconstruct reelsets

```bash
python main.py reelset
```

Prints a per-reel summary of inferred symbol weights and a candidate strip
order.  Saves `data/reelset_report.json`.

---

## Architecture

```
GameStatCollector/
├── main.py                   # CLI entry point (collect / analyse / reelset)
├── requirements.txt
├── collector/
│   ├── models.py             # Data models: Win, ReelState, SpinResult, GameStats
│   ├── browser.py            # Playwright browser launch & page setup
│   ├── game_frame.py         # Spin-button interaction inside the game iframe
│   ├── network_extractor.py  # HTTP response interception (primary data source)
│   ├── dom_extractor.py      # DOM-based fallback for symbol/win reading
│   ├── response_parser.py    # JSON payload parsers (Habanero & generic formats)
│   ├── stats.py              # Incremental statistics tracker
│   ├── storage.py            # NDJSON / JSON persistence
│   └── collector.py          # Orchestrator: runs the spin loop
├── analysis/
│   ├── win_stats.py          # Win-frequency analysis & WinReport
│   └── reelset.py            # Reelset reconstruction from observed sequences
├── data/                     # Collected data (gitignored)
└── tests/
    ├── test_models.py
    ├── test_stats.py
    ├── test_network.py
    └── test_reelset.py
```

### How data extraction works

1. **Network interception** (primary) – A Playwright browser-context listener
   captures every JSON HTTP response, including those from inside the game
   iframe.  Responses containing slot-game keywords (`reels`, `winlines`,
   `stops`, …) are passed through format-specific parsers.  Currently two
   parsers are registered:
   * **Habanero** – handles `data.reels` / `data.winLines` / `data.totalWin`
   * **Generic** – best-effort extraction from any JSON with a `reels` array

2. **DOM fallback** – If no parseable network response is found, the tool
   attempts to read win amounts and symbol names from the iframe's DOM.  This
   works for games that expose data via `data-symbol` attributes or ARIA
   labels.

3. **Raw storage** – Unrecognised payloads are written to
   `data/raw_responses.ndjson` so you can inspect them and add a new parser.

### Reelset reconstruction algorithm

Each spin produces a sequence of middle-row symbols on each reel.  The
reconstructor:

1. Builds a **bigram transition graph** – how often symbol A is followed by
   symbol B in the observed sequence.
2. Walks the graph greedily to produce a candidate **strip order**.
3. Scores **confidence** as the fraction of observed bigrams present in the
   reconstructed strip.

Confidence approaches 1.0 with more spins.  Practical accuracy requires
roughly 5 000–10 000 spins per reel.

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Notes

* The game must be playable in the browser (no sign-in required for the demo
  at slotstemple.com).
* The tool does **not** place real-money bets; it uses the free-play demo.
* `data/` is gitignored – collected datasets are kept locally only.
