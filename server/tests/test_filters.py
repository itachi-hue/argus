"""Tests for noise filtering."""

from argus.core.filters import NoiseFilter
from argus.core.models import ErrorEvent, NetworkEvent


class TestNetworkFiltering:
    def test_blocks_analytics(self):
        f = NoiseFilter()
        assert not f.should_keep_network("https://www.google-analytics.com/collect")
        assert not f.should_keep_network("https://cdn.segment.com/v1/track")
        assert not f.should_keep_network("https://browser-intake-datadoghq.com/logs")

    def test_keeps_app_requests(self):
        f = NoiseFilter()
        assert f.should_keep_network("http://localhost:3000/api/users")
        assert f.should_keep_network("https://api.myapp.com/v1/orders")

    def test_blocks_hmr(self):
        f = NoiseFilter()
        assert not f.should_keep_network("http://localhost:3000/__webpack_hmr")
        assert not f.should_keep_network("http://localhost:5173/__vite_ping")
        assert not f.should_keep_network("http://localhost:3000/_next/webpack-hmr")

    def test_blocks_favicon(self):
        f = NoiseFilter()
        assert not f.should_keep_network("http://localhost:3000/favicon.ico")

    def test_blocks_source_maps(self):
        f = NoiseFilter()
        assert not f.should_keep_network("http://localhost:3000/bundle.js.map")

    def test_blocks_extension_urls(self):
        f = NoiseFilter()
        assert not f.should_keep_network("chrome-extension://abc123/script.js")

    def test_subdomain_blocking(self):
        f = NoiseFilter()
        assert not f.should_keep_network("https://sub.sentry.io/api/123")
        assert not f.should_keep_network("https://deep.sub.google-analytics.com/collect")

    def test_allowed_domains_override(self):
        f = NoiseFilter(allowed_domains={"sentry.io"})
        assert f.should_keep_network("https://sentry.io/api/123")  # allowed overrides blocked

    def test_extra_blocked_domains(self):
        f = NoiseFilter(extra_blocked={"custom-analytics.com"})
        assert not f.should_keep_network("https://custom-analytics.com/track")

    def test_filter_batch(self):
        f = NoiseFilter()
        events = [
            NetworkEvent(method="GET", url="http://localhost:3000/api/data", status=200, timestamp=1.0),
            NetworkEvent(method="GET", url="https://google-analytics.com/collect", status=200, timestamp=2.0),
            NetworkEvent(method="GET", url="http://localhost:3000/favicon.ico", status=404, timestamp=3.0),
        ]
        kept = f.filter_network_events(events)
        assert len(kept) == 1
        assert kept[0].url == "http://localhost:3000/api/data"


class TestErrorFiltering:
    def test_blocks_extension_errors(self):
        f = NoiseFilter()
        assert not f.should_keep_error("chrome-extension://abc/script.js", "")
        assert not f.should_keep_error("moz-extension://abc/script.js", "")

    def test_keeps_app_errors(self):
        f = NoiseFilter()
        assert f.should_keep_error("http://localhost:3000/app.js", "at app.js:10:5")

    def test_blocks_all_extension_stack(self):
        f = NoiseFilter()
        stack = "at chrome-extension://abc/content.js:10:5\nat chrome-extension://abc/bg.js:20:3"
        assert not f.should_keep_error("", stack)

    def test_keeps_mixed_stack(self):
        f = NoiseFilter()
        stack = "at http://localhost:3000/app.js:10:5\nat chrome-extension://abc/inject.js:20:3"
        assert f.should_keep_error("http://localhost:3000/app.js", stack)

    def test_filter_batch(self):
        f = NoiseFilter()
        errors = [
            ErrorEvent(message="real error", source="http://localhost:3000/app.js",
                       stack="at app.js:10", timestamp=1.0),
            ErrorEvent(message="ext error", source="chrome-extension://abc/x.js",
                       stack="", timestamp=2.0),
        ]
        kept = f.filter_errors(errors)
        assert len(kept) == 1
        assert kept[0].message == "real error"



