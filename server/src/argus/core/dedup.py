"""Error deduplication within a time window."""

from argus.core.models import ErrorEvent


class ErrorDeduplicator:
    def __init__(self, window_seconds: float = 5.0):
        self.window = window_seconds
        self._seen: dict[str, ErrorEvent] = {}

    def _key(self, error: ErrorEvent) -> str:
        return f"{error.message}|{error.source}|{error.lineno}"

    def process(self, error: ErrorEvent) -> ErrorEvent | None:
        """Return the error if new, None if duplicate within window."""
        key = self._key(error)
        now = error.timestamp

        if key in self._seen:
            existing = self._seen[key]
            if now - existing.timestamp < self.window:
                existing.occurrence_count += 1
                return None

        self._seen[key] = error
        self._cleanup(now)
        return error

    def process_batch(self, errors: list[ErrorEvent]) -> list[ErrorEvent]:
        return [e for err in errors if (e := self.process(err)) is not None]

    def _cleanup(self, now: float) -> None:
        cutoff = now - self.window * 2
        expired = [k for k, v in self._seen.items() if v.timestamp < cutoff]
        for k in expired:
            del self._seen[k]

