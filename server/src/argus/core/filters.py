"""Noise filtering for network events and errors."""

import re
from urllib.parse import urlparse

BLOCKED_DOMAINS: set[str] = {
    # Analytics
    "google-analytics.com", "googletagmanager.com", "www.google-analytics.com",
    "ssl.google-analytics.com",
    # Facebook
    "facebook.net", "connect.facebook.net", "fbcdn.net",
    # Error tracking (we don't need to monitor the monitor)
    "sentry.io", "sentry-cdn.com", "browser.sentry-cdn.com",
    # Session replay / heatmaps
    "hotjar.com", "static.hotjar.com", "clarity.ms",
    "mouseflow.com", "smartlook.com",
    "fullstory.com", "rs.fullstory.com",
    "logrocket.com", "cdn.lr-ingest.io",
    # Product analytics
    "segment.com", "cdn.segment.com",
    "mixpanel.com", "cdn.mixpanel.com",
    "amplitude.com", "cdn.amplitude.com",
    "heap-analytics.com", "heapanalytics.com",
    "posthog.com", "plausible.io",
    # APM
    "newrelic.com", "js-agent.newrelic.com", "nr-data.net",
    "browser-intake-datadoghq.com",
    "rollbar.com", "cdn.rollbar.com",
    "bugsnag.com", "notify.bugsnag.com",
    # Chat / support
    "intercom.io", "widget.intercom.io",
    # Ads
    "doubleclick.net", "googlesyndication.com", "adservice.google.com",
}

_BLOCKED_URL_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"favicon\.ico$",
        r"\.hot-update\.",
        r"__webpack_hmr",
        r"sockjs-node",
        r"/_next/webpack-hmr",
        r"/vite-hmr",
        r"/__vite_ping",
        r"\.map$",
        r"^chrome-extension://",
        r"^moz-extension://",
    ]
]


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _domain_blocked(domain: str, blocked: set[str], allowed: set[str]) -> bool:
    if domain in allowed:
        return False
    if domain in blocked:
        return True
    # Check parent domains: sub.example.com → example.com
    parts = domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in allowed:
            return False
        if parent in blocked:
            return True
    return False


class NoiseFilter:
    def __init__(
        self,
        extra_blocked: set[str] | None = None,
        allowed_domains: set[str] | None = None,
    ):
        self.blocked = BLOCKED_DOMAINS | (extra_blocked or set())
        self.allowed = allowed_domains or set()

    def should_keep_network(self, url: str) -> bool:
        domain = _extract_domain(url)
        if _domain_blocked(domain, self.blocked, self.allowed):
            return False
        for pat in _BLOCKED_URL_PATTERNS:
            if pat.search(url):
                return False
        return True

    def should_keep_error(self, source: str, stack: str) -> bool:
        if source.startswith(("chrome-extension://", "moz-extension://")):
            return False
        # If stack exists and ALL frames are from blocked sources, skip
        if stack:
            frames = [line.strip() for line in stack.split("\n") if line.strip()]
            if frames and all(
                "chrome-extension://" in f or "moz-extension://" in f
                for f in frames
                if "at " in f or "@" in f
            ):
                return False
        return True

    def filter_network_events(self, events: list) -> list:
        return [e for e in events if self.should_keep_network(e.url)]

    def filter_errors(self, errors: list) -> list:
        return [e for e in errors if self.should_keep_error(e.source, e.stack)]



