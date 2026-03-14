"""Tests for stack trace parser."""

from argus.core.stack_parser import ParsedError, parse_error, parse_stack_trace


class TestParseStackTrace:
    def test_chrome_format(self):
        stack = """    at handleClick (http://localhost:3000/src/App.tsx:42:10)
    at HTMLButtonElement.callCallback (http://localhost:3000/node_modules/react-dom/cjs/react-dom.development.js:188:14)
    at Object.invokeGuardedCallbackDev (http://localhost:3000/node_modules/react-dom/cjs/react-dom.development.js:237:16)"""

        locs = parse_stack_trace(stack)
        assert len(locs) == 3

        assert locs[0].function_name == "handleClick"
        assert locs[0].file_path == "src/App.tsx"
        assert locs[0].line == 42
        assert locs[0].column == 10
        assert locs[0].is_app_code is True

        assert locs[1].is_app_code is False  # node_modules

    def test_chrome_no_function(self):
        stack = "    at http://localhost:3000/src/index.tsx:10:5"
        locs = parse_stack_trace(stack)
        assert len(locs) == 1
        assert locs[0].function_name == "<anonymous>"
        assert locs[0].file_path == "src/index.tsx"
        assert locs[0].line == 10

    def test_firefox_format(self):
        stack = """handleClick@http://localhost:5173/src/App.tsx:42:10
callCallback@http://localhost:5173/node_modules/react-dom/cjs/react-dom.development.js:188:14"""

        locs = parse_stack_trace(stack)
        assert len(locs) == 2
        assert locs[0].function_name == "handleClick"
        assert locs[0].file_path == "src/App.tsx"
        assert locs[0].line == 42
        assert locs[1].is_app_code is False

    def test_webpack_source_map(self):
        stack = "    at Component (webpack:///./src/components/Button.tsx:15:8)"
        locs = parse_stack_trace(stack)
        assert len(locs) == 1
        assert locs[0].file_path == "src/components/Button.tsx"
        assert locs[0].is_app_code is True

    def test_empty_stack(self):
        assert parse_stack_trace("") == []
        assert parse_stack_trace("TypeError: x is not a function") == []

    def test_chrome_extension_filtered(self):
        stack = "    at handleClick (chrome-extension://abc123/content.js:10:5)"
        locs = parse_stack_trace(stack)
        assert len(locs) == 1
        assert locs[0].is_app_code is False

    def test_cdn_filtered(self):
        stack = "    at run (https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js:1:1)"
        locs = parse_stack_trace(stack)
        assert len(locs) == 1
        assert locs[0].is_app_code is False


class TestParseError:
    def test_finds_primary_location(self):
        stack = """    at Object.invokeGuardedCallbackDev (http://localhost:3000/node_modules/react-dom/cjs/react-dom.development.js:237:16)
    at handleClick (http://localhost:3000/src/App.tsx:42:10)
    at HTMLButtonElement.callCallback (http://localhost:3000/node_modules/react-dom/cjs/react-dom.development.js:188:14)"""

        parsed = parse_error("TypeError: x is not a function", stack)
        assert isinstance(parsed, ParsedError)
        assert parsed.message == "TypeError: x is not a function"
        assert len(parsed.source_locations) == 3
        assert parsed.primary_location is not None
        assert parsed.primary_location.file_path == "src/App.tsx"
        assert parsed.primary_location.line == 42

    def test_no_app_code(self):
        stack = "    at handleClick (http://localhost:3000/node_modules/lib/index.js:10:5)"
        parsed = parse_error("Error", stack)
        assert parsed.primary_location is None

    def test_to_dict(self):
        parsed = parse_error("Error", "    at fn (http://localhost:3000/src/a.ts:1:1)")
        d = parsed.to_dict()
        assert d["message"] == "Error"
        assert len(d["locations"]) == 1
        assert d["primary"]["file"] == "src/a.ts"

