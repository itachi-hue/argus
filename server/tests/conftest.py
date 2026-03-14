"""Shared fixtures for all tests."""

import pytest
from fastapi.testclient import TestClient

from argus.api.server import create_app
from argus.config import Settings
from argus.core.dedup import ErrorDeduplicator
from argus.core.filters import NoiseFilter
from argus.security.sanitizer import Sanitizer
from argus.store.memory import InMemoryStore


@pytest.fixture
def config():
    return Settings(auth_token="test-token-12345", port=0)


@pytest.fixture
def store(config):
    return InMemoryStore(config)


@pytest.fixture
def noise_filter():
    return NoiseFilter()


@pytest.fixture
def deduplicator():
    return ErrorDeduplicator(window_seconds=5.0)


@pytest.fixture
def sanitizer():
    return Sanitizer(max_body_length=100)


@pytest.fixture
def app(store, config):
    return create_app(store, config)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token-12345"}


# --- Test data factories ---


def make_error(message="TypeError: x is not a function", source="app.js", lineno=42, timestamp=1000.0, **kw):
    return {
        "message": message,
        "source": source,
        "lineno": lineno,
        "colno": 10,
        "stack": f"  at {source}:{lineno}:10",
        "timestamp": timestamp,
        "occurrence_count": 1,
        **kw,
    }


def make_network(method="GET", url="http://localhost:3000/api/data", status=200, timestamp=1000.0, **kw):
    return {
        "method": method,
        "url": url,
        "status": status,
        "status_text": "OK" if status < 400 else "Error",
        "request_headers": kw.pop("request_headers", {}),
        "response_headers": kw.pop("response_headers", {}),
        "request_body": kw.pop("request_body", None),
        "response_body": kw.pop("response_body", None),
        "duration_ms": 50,
        "timestamp": timestamp,
        "error": kw.pop("error", None),
        **kw,
    }


def make_console(level="log", args=None, timestamp=1000.0, **kw):
    return {
        "level": level,
        "args": args if args is not None else ["hello world"],
        "timestamp": timestamp,
        "source": "",
        "lineno": 0,
        **kw,
    }


def make_screenshot(url="http://localhost:3000", timestamp=1000.0, trigger="hotkey"):
    return {
        "data": "dGVzdA==",
        "url": url,
        "timestamp": timestamp,
        "viewport": {"width": 1280, "height": 720},
        "trigger": trigger,
    }


def make_element(selector="button.submit", url="http://localhost:3000/checkout", timestamp=1000.0):
    return {
        "selector": selector,
        "computed_styles": {"display": "flex", "color": "rgb(255,255,255)", "font-size": "14px"},
        "html": '<button class="submit">Submit</button>',
        "text": "Submit",
        "bounding_rect": {"x": 100, "y": 200, "width": 150, "height": 40},
        "parent_html": '<form class="checkout-form">...</form>',
        "timestamp": timestamp,
        "url": url,
    }


def make_page_info(url="http://localhost:3000/checkout", title="Checkout", timestamp=1000.0):
    return {
        "url": url,
        "title": title,
        "viewport": {"width": 1920, "height": 1080},
        "timestamp": timestamp,
    }
