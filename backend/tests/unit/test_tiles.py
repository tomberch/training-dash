"""Unit tests for the tiles router security functions."""

from pathlib import Path

import pytest

from trainingdash.routers.tiles import _safe_cache_path


class TestSafeCachePath:
    """Tests for the _safe_cache_path function that prevents path traversal."""

    def test_valid_path_within_base(self, tmp_path: Path):
        """Normal tile paths should work."""
        result = _safe_cache_path(tmp_path, "10", "512", "512.png")
        assert result == tmp_path / "10" / "512" / "512.png"

    def test_valid_carto_path(self, tmp_path: Path):
        """Carto-style paths with style subdirectory should work."""
        result = _safe_cache_path(tmp_path, "carto", "light", "10", "512", "512.png")
        assert result == tmp_path / "carto" / "light" / "10" / "512" / "512.png"

    def test_path_traversal_single_dotdot_rejected(self, tmp_path: Path):
        """Paths with .. should be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            _safe_cache_path(tmp_path, "..", "etc", "passwd")

    def test_path_traversal_nested_dotdot_rejected(self, tmp_path: Path):
        """Paths with nested .. should be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            _safe_cache_path(tmp_path, "10", "..", "..", "etc", "passwd")

    def test_path_traversal_hidden_in_middle_rejected(self, tmp_path: Path):
        """Paths with .. hidden in the middle should be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            _safe_cache_path(tmp_path, "10", "512", "..", "..", "..", "etc", "passwd")

    def test_absolute_path_component_rejected(self, tmp_path: Path):
        """Absolute path components should be rejected (resolved away)."""
        # On POSIX, joining with an absolute path replaces the base
        # The resolve() + is_relative_to() check catches this
        with pytest.raises(ValueError, match="traversal"):
            _safe_cache_path(tmp_path, "/etc/passwd")

    def test_empty_parts_allowed(self, tmp_path: Path):
        """Empty parts should be handled (Path ignores them)."""
        result = _safe_cache_path(tmp_path, "10", "", "512.png")
        # Path.joinpath ignores empty strings
        assert result == tmp_path / "10" / "512.png"

    def test_result_is_resolved(self, tmp_path: Path):
        """Result should be an absolute resolved path."""
        result = _safe_cache_path(tmp_path, "10", "512", "512.png")
        assert result.is_absolute()
        assert ".." not in str(result)
