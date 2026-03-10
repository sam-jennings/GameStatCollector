"""Tests for browser frame selection helpers."""

from __future__ import annotations

from types import SimpleNamespace

from collector.browser import _find_game_frame_by_url, _frame_looks_like_game_url


def test_frame_looks_like_game_url_matches_habanero_host():
    assert _frame_looks_like_game_url("https://cdn.habanerosystems.com/game/launch") is True


def test_frame_looks_like_game_url_rejects_non_game_url():
    assert _frame_looks_like_game_url("https://www.google.com/ads") is False


def test_find_game_frame_by_url_returns_non_main_game_frame():
    main = SimpleNamespace(url="https://www.slotstemple.com/us/free-slots/mystic-fortune")
    non_game = SimpleNamespace(url="https://www.google.com/recaptcha")
    game = SimpleNamespace(url="https://games.example.com/slot/launch")
    page = SimpleNamespace(main_frame=main, frames=[main, non_game, game])

    assert _find_game_frame_by_url(page) is game
