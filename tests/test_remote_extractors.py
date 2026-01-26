"""Tests for remote extractor fetching and caching."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.research.remote import get_extractor_js, clear_cache, CACHE_DIR, CACHE_TTL


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Use temporary directory for cache."""
    cache_dir = tmp_path / "extractors"
    with patch("scripts.research.remote.CACHE_DIR", cache_dir):
        yield cache_dir


class TestGetExtractorJs:
    """Tests for get_extractor_js function."""

    def test_fetches_from_github_when_no_cache(self, temp_cache_dir):
        """Fetches JS from GitHub when cache is empty."""
        mock_response = MagicMock()
        mock_response.text = "() => { return {}; }"
        mock_response.raise_for_status = MagicMock()

        with patch("scripts.research.remote.requests.get", return_value=mock_response) as mock_get:
            result = get_extractor_js("glassdoor")

        assert result == "() => { return {}; }"
        mock_get.assert_called_once()
        assert "glassdoor.js" in mock_get.call_args[0][0]

    def test_uses_cache_when_fresh(self, temp_cache_dir):
        """Uses cached JS when cache is fresh (< 1 hour)."""
        cache_file = temp_cache_dir / "glassdoor.js"
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("() => { return {cached: true}; }")

        with patch("scripts.research.remote.requests.get") as mock_get:
            result = get_extractor_js("glassdoor")

        assert result == "() => { return {cached: true}; }"
        mock_get.assert_not_called()  # Should not hit network

    def test_refetches_when_cache_stale(self, temp_cache_dir):
        """Refetches from GitHub when cache is stale (> 1 hour)."""
        cache_file = temp_cache_dir / "glassdoor.js"
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("() => { return {old: true}; }")

        # Make cache file appear old
        old_time = time.time() - CACHE_TTL - 100
        import os
        os.utime(cache_file, (old_time, old_time))

        mock_response = MagicMock()
        mock_response.text = "() => { return {new: true}; }"
        mock_response.raise_for_status = MagicMock()

        with patch("scripts.research.remote.requests.get", return_value=mock_response):
            result = get_extractor_js("glassdoor")

        assert result == "() => { return {new: true}; }"

    def test_falls_back_to_stale_cache_on_network_error(self, temp_cache_dir):
        """Falls back to stale cache when network fails."""
        cache_file = temp_cache_dir / "glassdoor.js"
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("() => { return {stale: true}; }")

        # Make cache file appear old
        old_time = time.time() - CACHE_TTL - 100
        import os
        os.utime(cache_file, (old_time, old_time))

        with patch("scripts.research.remote.requests.get", side_effect=Exception("Network error")):
            result = get_extractor_js("glassdoor")

        assert result == "() => { return {stale: true}; }"

    def test_raises_when_no_cache_and_network_fails(self, temp_cache_dir):
        """Raises RuntimeError when both cache and network unavailable."""
        with patch("scripts.research.remote.requests.get", side_effect=Exception("Network error")):
            with pytest.raises(RuntimeError) as exc_info:
                get_extractor_js("nonexistent")

        assert "Cannot fetch nonexistent extractor" in str(exc_info.value)


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clears_single_extractor(self, temp_cache_dir):
        """Clears cache for single extractor."""
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        (temp_cache_dir / "glassdoor.js").write_text("test")
        (temp_cache_dir / "crunchbase.js").write_text("test")

        clear_cache("glassdoor")

        assert not (temp_cache_dir / "glassdoor.js").exists()
        assert (temp_cache_dir / "crunchbase.js").exists()

    def test_clears_all_extractors(self, temp_cache_dir):
        """Clears cache for all extractors when source is None."""
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        (temp_cache_dir / "glassdoor.js").write_text("test")
        (temp_cache_dir / "crunchbase.js").write_text("test")

        clear_cache()

        assert not (temp_cache_dir / "glassdoor.js").exists()
        assert not (temp_cache_dir / "crunchbase.js").exists()

    def test_handles_missing_cache_dir(self, temp_cache_dir):
        """Does not raise when cache directory doesn't exist."""
        clear_cache()  # Should not raise
        clear_cache("glassdoor")  # Should not raise
