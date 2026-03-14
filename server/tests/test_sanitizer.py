"""Tests for sensitive data sanitization."""

from argus.core.models import NetworkEvent
from argus.security.sanitizer import Sanitizer


class TestHeaderSanitization:
    def test_redacts_auth_header(self):
        s = Sanitizer()
        headers = {"Authorization": "Bearer secret123", "Content-Type": "application/json"}
        sanitized = s.sanitize_headers(headers)
        assert sanitized["Authorization"] == "[REDACTED]"
        assert sanitized["Content-Type"] == "application/json"

    def test_redacts_cookies(self):
        s = Sanitizer()
        headers = {"Cookie": "session=abc123", "Set-Cookie": "token=xyz"}
        sanitized = s.sanitize_headers(headers)
        assert sanitized["Cookie"] == "[REDACTED]"
        assert sanitized["Set-Cookie"] == "[REDACTED]"

    def test_redacts_api_keys(self):
        s = Sanitizer()
        headers = {"X-API-Key": "sk-123", "X-Auth-Token": "tok-456"}
        sanitized = s.sanitize_headers(headers)
        assert sanitized["X-API-Key"] == "[REDACTED]"
        assert sanitized["X-Auth-Token"] == "[REDACTED]"

    def test_case_insensitive(self):
        s = Sanitizer()
        headers = {"authorization": "Bearer x", "COOKIE": "y"}
        sanitized = s.sanitize_headers(headers)
        assert sanitized["authorization"] == "[REDACTED]"
        assert sanitized["COOKIE"] == "[REDACTED]"


class TestBodyTruncation:
    def test_short_body_unchanged(self):
        s = Sanitizer(max_body_length=100)
        assert s.truncate("short") == "short"

    def test_long_body_truncated(self):
        s = Sanitizer(max_body_length=10)
        result = s.truncate("a" * 50)
        assert len(result) < 50
        assert result.startswith("aaaaaaaaaa")
        assert "truncated" in result

    def test_none_body(self):
        s = Sanitizer()
        assert s.truncate(None) is None


class TestNetworkEventSanitization:
    def test_full_sanitization(self):
        s = Sanitizer(max_body_length=20)
        event = NetworkEvent(
            method="POST", url="http://localhost/api", status=200, timestamp=1.0,
            request_headers={"Authorization": "Bearer secret", "Accept": "application/json"},
            response_headers={"Set-Cookie": "session=abc"},
            request_body="a" * 100,
            response_body='{"data": "sensitive user info that is very long"}',
        )
        sanitized = s.sanitize_network_event(event)
        assert sanitized.request_headers["Authorization"] == "[REDACTED]"
        assert sanitized.request_headers["Accept"] == "application/json"
        assert sanitized.response_headers["Set-Cookie"] == "[REDACTED]"
        assert len(sanitized.request_body) < 100
        assert len(sanitized.response_body) < 100

    def test_batch_sanitization(self):
        s = Sanitizer()
        events = [
            NetworkEvent(method="GET", url="http://x/a", timestamp=1.0,
                         request_headers={"Authorization": "Bearer x"}),
            NetworkEvent(method="GET", url="http://x/b", timestamp=2.0,
                         request_headers={"Authorization": "Bearer y"}),
        ]
        sanitized = s.sanitize_network_events(events)
        assert all(e.request_headers.get("Authorization") == "[REDACTED]" for e in sanitized)




