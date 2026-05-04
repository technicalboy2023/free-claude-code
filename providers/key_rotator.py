"""Thread-safe round-robin API key rotator.

Each provider instance holds one ``KeyRotator`` with all configured keys.
On every request the rotator returns the next key in round-robin order,
distributing load evenly and recovering from per-key rate limits.
"""

from __future__ import annotations

import threading

from loguru import logger


class KeyRotator:
    """Cycle through a list of API keys in round-robin order.

    The rotator is safe for concurrent asyncio tasks because the
    index is advanced under a lightweight ``threading.Lock``.
    """

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("KeyRotator requires at least one API key")
        # Strip and deduplicate while preserving order
        seen: set[str] = set()
        clean: list[str] = []
        for key in keys:
            k = key.strip()
            if k and k not in seen:
                seen.add(k)
                clean.append(k)
        if not clean:
            raise ValueError("KeyRotator: all provided keys are empty")
        self._keys: list[str] = clean
        self._index: int = 0
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_key(self) -> str:
        """Return the next API key in round-robin order."""
        with self._lock:
            key = self._keys[self._index]
            self._index = (self._index + 1) % len(self._keys)
        return key

    @property
    def key_count(self) -> int:
        """Return the total number of unique keys."""
        return len(self._keys)

    @property
    def first_key(self) -> str:
        """Return the first key (used for backwards-compatible single-key paths)."""
        return self._keys[0]

    def log_summary(self, provider_name: str) -> None:
        """Emit an INFO log showing key count (never the keys themselves)."""
        if self.key_count > 1:
            logger.info(
                "KEY_ROTATION: provider={} keys={} mode=round_robin",
                provider_name,
                self.key_count,
            )
        else:
            logger.info(
                "KEY_ROTATION: provider={} keys=1 mode=single",
                provider_name,
            )

    def __repr__(self) -> str:
        return f"KeyRotator(keys={self.key_count})"


def parse_key_string(raw: str) -> list[str]:
    """Parse a comma-separated key string into a list of non-empty keys.

    Supports both single key (``"sk-abc"``) and multi-key
    (``"sk-abc,sk-def,sk-ghi"``) formats.
    """
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def rotator_from_env_value(raw: str) -> KeyRotator | None:
    """Build a ``KeyRotator`` from a raw env variable value, or ``None`` if empty."""
    keys = parse_key_string(raw)
    if not keys:
        return None
    return KeyRotator(keys)
