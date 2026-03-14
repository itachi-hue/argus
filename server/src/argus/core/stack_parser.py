"""Stack trace parser — extracts structured source locations from JS stack traces.

Parses Chrome, Firefox, and Safari stack trace formats into structured
file:line:column entries with workspace-relative path mapping.
"""

import re
from dataclasses import dataclass, field

# Chrome/V8:  "    at functionName (http://localhost:3000/src/App.tsx:42:10)"
#             "    at http://localhost:3000/src/App.tsx:42:10"
CHROME_RE = re.compile(
    r"^\s*at\s+(?:(?P<func>[^\s(]+)\s+)?\(?(?P<url>[^)\s]+):(?P<line>\d+):(?P<col>\d+)\)?",
)

# Firefox:    "functionName@http://localhost:3000/src/App.tsx:42:10"
FIREFOX_RE = re.compile(
    r"^\s*(?P<func>[^@]*)@(?P<url>.+):(?P<line>\d+):(?P<col>\d+)\s*$",
)

# Webpack internal:  "webpack:///./src/components/Button.tsx:15:8"
WEBPACK_RE = re.compile(r"^webpack:///\.?/?(.+)$")

# Common localhost URL prefix
LOCALHOST_RE = re.compile(r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?/(.+)$")

# Next.js path prefix
NEXTJS_RE = re.compile(r"^https?://[^/]+/_next/static/\w+/pages/(.+)$")

# Strip query string and hash from URLs
STRIP_QS_RE = re.compile(r"[?#].*$")


@dataclass
class SourceLocation:
    """A single stack frame parsed from a JS stack trace."""

    function_name: str
    url: str
    line: int
    column: int
    file_path: str  # workspace-relative path (best effort)
    is_app_code: bool  # True if likely from the user's app (not node_modules, CDN, etc.)

    def to_dict(self) -> dict:
        return {
            "function": self.function_name,
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "url": self.url,
            "is_app_code": self.is_app_code,
        }


@dataclass
class ParsedError:
    """A fully parsed error with structured source locations."""

    message: str
    source_locations: list[SourceLocation] = field(default_factory=list)
    primary_location: SourceLocation | None = None  # Most likely user code location

    def to_dict(self) -> dict:
        result: dict = {
            "message": self.message,
            "locations": [loc.to_dict() for loc in self.source_locations],
        }
        if self.primary_location:
            result["primary"] = self.primary_location.to_dict()
        return result


def _url_to_file_path(url: str) -> str:
    """Best-effort map a URL to a workspace-relative file path."""
    url = STRIP_QS_RE.sub("", url)

    # webpack:///./src/App.tsx → src/App.tsx
    m = WEBPACK_RE.match(url)
    if m:
        return m.group(1)

    # Next.js: /_next/static/.../pages/index.js → pages/index.js
    m = NEXTJS_RE.match(url)
    if m:
        return m.group(1)

    # http://localhost:3000/src/App.tsx → src/App.tsx
    m = LOCALHOST_RE.match(url)
    if m:
        path = m.group(1)
        # Strip common build prefixes
        for prefix in ("static/js/", "static/", "assets/", "_next/"):
            if path.startswith(prefix):
                return path
        return path

    # Already a file path
    if not url.startswith("http"):
        return url

    return url


def _is_app_code(url: str, file_path: str) -> bool:
    """Heuristic: is this frame from the user's app or third-party?"""
    skip_patterns = (
        "node_modules",
        "cdn.",
        "cdnjs.",
        "unpkg.com",
        "jsdelivr.net",
        "googleapis.com",
        "polyfill",
        "chrome-extension://",
        "moz-extension://",
        "<anonymous>",
        "webpack/bootstrap",
        "webpack/runtime",
        "react-dom",
        "react.production",
        "react.development",
        "scheduler.development",
        "scheduler.production",
        "vendor.",
        "chunk-vendors",
    )
    combined = url + file_path
    return not any(p in combined.lower() for p in skip_patterns)


def parse_stack_trace(stack: str) -> list[SourceLocation]:
    """Parse a JavaScript stack trace into structured source locations."""
    locations: list[SourceLocation] = []

    for line in stack.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try Chrome format first
        m = CHROME_RE.match(line)
        if not m:
            m = FIREFOX_RE.match(line)
        if not m:
            continue

        func = m.group("func") or "<anonymous>"
        url = m.group("url")
        line_no = int(m.group("line"))
        col = int(m.group("col"))
        file_path = _url_to_file_path(url)
        app_code = _is_app_code(url, file_path)

        locations.append(
            SourceLocation(
                function_name=func,
                url=url,
                line=line_no,
                column=col,
                file_path=file_path,
                is_app_code=app_code,
            )
        )

    return locations


def parse_error(message: str, stack: str) -> ParsedError:
    """Parse an error message and stack trace into a structured ParsedError."""
    locations = parse_stack_trace(stack)

    # Find the primary location (first app code frame)
    primary = None
    for loc in locations:
        if loc.is_app_code:
            primary = loc
            break

    return ParsedError(
        message=message,
        source_locations=locations,
        primary_location=primary,
    )

