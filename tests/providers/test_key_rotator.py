"""Tests for round-robin API key rotation."""

from __future__ import annotations

import threading

import pytest

from providers.key_rotator import KeyRotator, parse_key_string, rotator_from_env_value

# ---------------------------------------------------------------------------
# parse_key_string
# ---------------------------------------------------------------------------


class TestParseKeyString:
    def test_single_key(self) -> None:
        assert parse_key_string("sk-abc") == ["sk-abc"]

    def test_multiple_keys(self) -> None:
        assert parse_key_string("sk-1,sk-2,sk-3") == ["sk-1", "sk-2", "sk-3"]

    def test_strips_whitespace(self) -> None:
        assert parse_key_string(" sk-1 , sk-2 , sk-3 ") == ["sk-1", "sk-2", "sk-3"]

    def test_skips_empty_segments(self) -> None:
        assert parse_key_string("sk-1,,sk-2,,,sk-3") == ["sk-1", "sk-2", "sk-3"]

    def test_empty_string(self) -> None:
        assert parse_key_string("") == []

    def test_only_commas(self) -> None:
        assert parse_key_string(",,,") == []


# ---------------------------------------------------------------------------
# KeyRotator
# ---------------------------------------------------------------------------


class TestKeyRotator:
    def test_single_key_always_returns_same(self) -> None:
        rotator = KeyRotator(["sk-only"])
        for _ in range(5):
            assert rotator.next_key() == "sk-only"

    def test_round_robin_cycles(self) -> None:
        rotator = KeyRotator(["k1", "k2", "k3"])
        results = [rotator.next_key() for _ in range(9)]
        assert results == ["k1", "k2", "k3", "k1", "k2", "k3", "k1", "k2", "k3"]

    def test_key_count(self) -> None:
        rotator = KeyRotator(["a", "b", "c"])
        assert rotator.key_count == 3

    def test_first_key(self) -> None:
        rotator = KeyRotator(["first", "second"])
        assert rotator.first_key == "first"

    def test_deduplicates_keys(self) -> None:
        rotator = KeyRotator(["k1", "k2", "k1", "k2"])
        assert rotator.key_count == 2
        assert rotator.next_key() == "k1"
        assert rotator.next_key() == "k2"
        assert rotator.next_key() == "k1"

    def test_strips_whitespace(self) -> None:
        rotator = KeyRotator(["  k1  ", "  k2  "])
        assert rotator.next_key() == "k1"
        assert rotator.next_key() == "k2"

    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            KeyRotator([])

    def test_all_empty_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="all provided keys are empty"):
            KeyRotator(["", "  ", ""])

    def test_thread_safety(self) -> None:
        """Verify no crashes under concurrent access."""
        rotator = KeyRotator(["k1", "k2", "k3"])
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(100):
                key = rotator.next_key()
                with lock:
                    results.append(key)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 400
        assert set(results) == {"k1", "k2", "k3"}

    def test_repr(self) -> None:
        rotator = KeyRotator(["a", "b"])
        assert repr(rotator) == "KeyRotator(keys=2)"


# ---------------------------------------------------------------------------
# rotator_from_env_value
# ---------------------------------------------------------------------------


class TestRotatorFromEnvValue:
    def test_single_key(self) -> None:
        rotator = rotator_from_env_value("sk-abc")
        assert rotator is not None
        assert rotator.key_count == 1
        assert rotator.next_key() == "sk-abc"

    def test_multi_key(self) -> None:
        rotator = rotator_from_env_value("sk-1,sk-2,sk-3")
        assert rotator is not None
        assert rotator.key_count == 3

    def test_empty_returns_none(self) -> None:
        assert rotator_from_env_value("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert rotator_from_env_value("   ") is None
