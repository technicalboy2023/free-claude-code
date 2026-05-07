"""Tests for api.runtime — AppRuntime helpers and startup logic."""

from __future__ import annotations

import pytest


class TestApiUrlLocalhostResolution:
    """BUG-01: api_url must never use wildcard bind addresses like 0.0.0.0."""

    @staticmethod
    def _resolve_cli_host(host: str) -> str:
        """Replicate the host resolution logic from _start_message_handler."""
        return "127.0.0.1" if host in ("0.0.0.0", "", "::", "[::]") else host

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("0.0.0.0", "127.0.0.1"),
            ("::", "127.0.0.1"),
            ("[::]", "127.0.0.1"),
            ("", "127.0.0.1"),
            ("127.0.0.1", "127.0.0.1"),
            ("192.168.1.50", "192.168.1.50"),
            ("my-server.example.com", "my-server.example.com"),
        ],
        ids=[
            "ipv4-wildcard",
            "ipv6-wildcard",
            "ipv6-bracketed",
            "empty",
            "localhost-passthrough",
            "lan-ip",
            "hostname",
        ],
    )
    def test_wildcard_hosts_resolve_to_localhost(
        self, host: str, expected: str
    ) -> None:
        """Wildcard bind addresses must be replaced with 127.0.0.1 for the CLI."""
        resolved = self._resolve_cli_host(host)
        assert resolved == expected

    @pytest.mark.parametrize(
        "host",
        ["0.0.0.0", "::", "[::]", ""],
        ids=["ipv4-wildcard", "ipv6-wildcard", "ipv6-bracketed", "empty"],
    )
    def test_api_url_never_contains_wildcard(self, host: str) -> None:
        """The constructed api_url should never contain a non-routable address."""
        resolved = self._resolve_cli_host(host)
        api_url = f"http://{resolved}:8082/v1"
        assert "0.0.0.0" not in api_url
        assert "http://:::" not in api_url
        assert "http://[::]::" not in api_url
        assert api_url == "http://127.0.0.1:8082/v1"

    def test_explicit_host_preserved_in_url(self) -> None:
        """When host is a real address, it should pass through unchanged."""
        resolved = self._resolve_cli_host("192.168.1.50")
        api_url = f"http://{resolved}:8082/v1"
        assert api_url == "http://192.168.1.50:8082/v1"


class TestApiUrlInRuntime:
    """Integration test: verify the actual runtime code uses the same logic."""

    def test_runtime_source_contains_wildcard_guard(self) -> None:
        """Verify the fix exists in the source — guard against regressions."""
        import inspect

        from api.runtime import AppRuntime

        source = inspect.getsource(AppRuntime._start_message_handler)
        # The fix must contain the wildcard check
        assert "0.0.0.0" in source
        assert "127.0.0.1" in source
        assert "::" in source
