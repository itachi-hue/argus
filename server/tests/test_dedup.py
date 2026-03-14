"""Tests for error deduplication."""

from argus.core.dedup import ErrorDeduplicator
from argus.core.models import ErrorEvent


class TestDeduplication:
    def test_first_occurrence_kept(self):
        d = ErrorDeduplicator(window_seconds=5)
        e = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1000.0)
        result = d.process(e)
        assert result is not None
        assert result.message == "err"

    def test_duplicate_within_window_skipped(self):
        d = ErrorDeduplicator(window_seconds=5)
        e1 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1000.0)
        e2 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1002.0)
        d.process(e1)
        result = d.process(e2)
        assert result is None

    def test_duplicate_increments_count(self):
        d = ErrorDeduplicator(window_seconds=5)
        e1 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1000.0)
        e2 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1002.0)
        e3 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1003.0)
        d.process(e1)
        d.process(e2)
        d.process(e3)
        assert e1.occurrence_count == 3

    def test_different_error_kept(self):
        d = ErrorDeduplicator(window_seconds=5)
        e1 = ErrorEvent(message="err1", source="app.js", lineno=10, timestamp=1000.0)
        e2 = ErrorEvent(message="err2", source="app.js", lineno=20, timestamp=1001.0)
        assert d.process(e1) is not None
        assert d.process(e2) is not None

    def test_after_window_expires_kept(self):
        d = ErrorDeduplicator(window_seconds=5)
        e1 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1000.0)
        e2 = ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1010.0)  # 10s later
        d.process(e1)
        result = d.process(e2)
        assert result is not None

    def test_process_batch(self):
        d = ErrorDeduplicator(window_seconds=5)
        errors = [
            ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1000.0),
            ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1001.0),  # dup
            ErrorEvent(message="err", source="app.js", lineno=10, timestamp=1002.0),  # dup
            ErrorEvent(message="other", source="app.js", lineno=20, timestamp=1003.0),  # different
        ]
        kept = d.process_batch(errors)
        assert len(kept) == 2
        assert kept[0].occurrence_count == 3

