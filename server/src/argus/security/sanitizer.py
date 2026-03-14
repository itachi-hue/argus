"""Sensitive data stripping for network events."""

from argus.core.models import NetworkEvent

SENSITIVE_HEADERS = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "proxy-authorization",
    "x-csrf-token",
    "x-xsrf-token",
})


class Sanitizer:
    def __init__(self, max_body_length: int = 2000):
        self.max_body = max_body_length

    def sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            k: "[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v
            for k, v in headers.items()
        }

    def truncate(self, text: str | None) -> str | None:
        if text is None:
            return None
        if len(text) <= self.max_body:
            return text
        return text[: self.max_body] + f"... [truncated, {len(text)} chars total]"

    def sanitize_network_event(self, event: NetworkEvent) -> NetworkEvent:
        return event.model_copy(
            update={
                "request_headers": self.sanitize_headers(event.request_headers),
                "response_headers": self.sanitize_headers(event.response_headers),
                "request_body": self.truncate(event.request_body),
                "response_body": self.truncate(event.response_body),
            }
        )

    def sanitize_network_events(self, events: list[NetworkEvent]) -> list[NetworkEvent]:
        return [self.sanitize_network_event(e) for e in events]




