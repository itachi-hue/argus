"""Tests for baseline storage and visual comparison."""

import base64
import io

from PIL import Image

from argus.core.baselines import BaselineStore, compare_screenshots


def _make_image(width: int = 100, height: int = 100, color: tuple = (255, 0, 0)) -> str:
    """Create a solid-color test image as base64 JPEG."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class TestBaselineStore:
    def test_save_and_get(self):
        store = BaselineStore()
        data = _make_image()
        store.save("test", data)
        assert store.get("test") == data

    def test_get_missing(self):
        store = BaselineStore()
        assert store.get("missing") is None

    def test_list_names(self):
        store = BaselineStore()
        store.save("a", _make_image())
        store.save("b", _make_image())
        names = store.list_names()
        assert "a" in names
        assert "b" in names

    def test_delete(self):
        store = BaselineStore()
        store.save("x", _make_image())
        assert store.delete("x") is True
        assert store.get("x") is None
        assert store.delete("x") is False

    def test_clear(self):
        store = BaselineStore()
        store.save("a", _make_image())
        store.save("b", _make_image())
        store.clear()
        assert store.list_names() == []

    def test_max_baselines(self):
        store = BaselineStore(max_baselines=3)
        for i in range(5):
            store.save(f"b{i}", _make_image())
        assert len(store.list_names()) == 3


class TestCompareScreenshots:
    def test_identical_images(self):
        img = _make_image(color=(100, 100, 100))
        result = compare_screenshots(img, img)
        assert result["match"] is True
        assert result["change_percent"] == 0.0
        assert result["changed_pixels"] == 0

    def test_different_images(self):
        a = _make_image(color=(255, 0, 0))
        b = _make_image(color=(0, 255, 0))
        result = compare_screenshots(a, b)
        assert result["match"] is False
        assert result["change_percent"] > 50
        assert result["changed_pixels"] > 0
        assert "diff_image" in result

    def test_slightly_different(self):
        a = _make_image(color=(100, 100, 100))
        b = _make_image(color=(105, 100, 100))
        result = compare_screenshots(a, b)
        # Very small change should be under threshold
        assert result["change_percent"] < 1.0

    def test_different_sizes_resized(self):
        a = _make_image(width=100, height=100, color=(255, 0, 0))
        b = _make_image(width=200, height=200, color=(255, 0, 0))
        result = compare_screenshots(a, b)
        # After resize, should be similar (JPEG artifacts may cause small diff)
        assert result["change_percent"] < 5.0

    def test_diff_image_is_valid_base64(self):
        a = _make_image(color=(255, 0, 0))
        b = _make_image(color=(0, 0, 255))
        result = compare_screenshots(a, b)
        # Should be valid base64 that decodes to a JPEG
        raw = base64.b64decode(result["diff_image"])
        img = Image.open(io.BytesIO(raw))
        assert img.format == "JPEG"
