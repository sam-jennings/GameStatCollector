"""Tests for NetworkExtractor and response_parser."""

from __future__ import annotations

import pytest

from collector.network_extractor import NetworkExtractor
from collector.response_parser import parse_spin


# ---------------------------------------------------------------------------
# NetworkExtractor
# ---------------------------------------------------------------------------

class TestNetworkExtractor:
    def test_no_spin_responses_initially(self):
        ext = NetworkExtractor()
        assert ext.pop_latest_spin() is None

    def test_clear_removes_all(self):
        ext = NetworkExtractor()
        # Simulate adding a response directly
        ext._spin_responses.append({"url": "http://x", "body": {}})
        ext.clear()
        assert ext.pop_latest_spin() is None

    def test_looks_like_spin_result_true(self):
        body = {"reels": [["A", "B"]], "totalWin": 0}
        assert NetworkExtractor._looks_like_spin_result(body) is True

    def test_looks_like_spin_result_false(self):
        body = {"user": "test", "token": "abc123"}
        assert NetworkExtractor._looks_like_spin_result(body) is False

    def test_looks_like_spin_result_nested(self):
        body = {"data": {"result": {"reels": [["A"]]}}}
        assert NetworkExtractor._looks_like_spin_result(body) is True


# ---------------------------------------------------------------------------
# response_parser – Habanero format
# ---------------------------------------------------------------------------

_HABANERO_PAYLOAD = {
    "data": {
        "reels": [
            ["WILD", "A", "B"],
            ["WILD", "C", "D"],
            ["WILD", "E", "F"],
            ["G", "H", "I"],
            ["J", "K", "L"],
        ],
        "winLines": [
            {
                "lineIndex": 0,
                "symbolId": "WILD",
                "symbolCount": 3,
                "positions": [[0, 1], [1, 1], [2, 1]],
                "lineWin": 5.0,
            }
        ],
        "totalWin": 5.0,
    }
}

_GENERIC_PAYLOAD = {
    "reels": [
        ["A", "B", "C"],
        ["D", "E", "F"],
    ],
    "wins": [
        {
            "symbol": "A",
            "count": 2,
            "positions": [[0, 0], [1, 0]],
            "win": 1.0,
        }
    ],
    "totalwin": 1.0,
}


class TestResponseParser:
    def test_habanero_parses_reels(self):
        result = parse_spin(_HABANERO_PAYLOAD, spin_id=1, bet_amount=1.0)
        assert result is not None
        assert result.reel_state.num_reels == 5
        assert result.reel_state.symbols[0] == ["WILD", "A", "B"]

    def test_habanero_parses_wins(self):
        result = parse_spin(_HABANERO_PAYLOAD, spin_id=1, bet_amount=1.0)
        assert result is not None
        assert len(result.wins) == 1
        win = result.wins[0]
        assert win.symbol == "WILD"
        assert win.count == 3
        assert win.amount == pytest.approx(5.0)
        assert win.reels == [0, 1, 2]

    def test_habanero_total_win(self):
        result = parse_spin(_HABANERO_PAYLOAD, spin_id=1, bet_amount=1.0)
        assert result is not None
        assert result.total_win == pytest.approx(5.0)

    def test_generic_parses_reels(self):
        result = parse_spin(_GENERIC_PAYLOAD, spin_id=2, bet_amount=1.0)
        assert result is not None
        assert result.reel_state.num_reels == 2
        assert result.reel_state.symbols[0] == ["A", "B", "C"]

    def test_generic_parses_wins(self):
        result = parse_spin(_GENERIC_PAYLOAD, spin_id=2, bet_amount=1.0)
        assert result is not None
        assert len(result.wins) == 1
        assert result.wins[0].symbol == "A"

    def test_unrecognised_payload_returns_none(self):
        result = parse_spin({"foo": "bar", "baz": 42}, spin_id=3, bet_amount=1.0)
        assert result is None

    def test_spin_id_preserved(self):
        result = parse_spin(_HABANERO_PAYLOAD, spin_id=99, bet_amount=1.0)
        assert result is not None
        assert result.spin_id == 99

    def test_raw_data_stored(self):
        result = parse_spin(_HABANERO_PAYLOAD, spin_id=1, bet_amount=1.0)
        assert result is not None
        assert result.raw_data is _HABANERO_PAYLOAD
