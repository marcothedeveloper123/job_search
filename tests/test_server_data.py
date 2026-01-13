"""Tests for server data layer functions."""

import json
from unittest.mock import patch

import pytest

from server.data import (
    Job,
    SearchResults,
    SearchParams,
    Selections,
    remove_jobs,
    remove_deep_dives,
    update_job,
    get_selections,
    get_deep_dives,
    save_deep_dive,
    DeepDive,
    DeepDives,
    JobNotFoundError,
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temp directory for test data files."""
    results_file = tmp_path / "results.json"
    deep_dives_file = tmp_path / "deep_dives.json"
    return tmp_path, results_file, deep_dives_file


class TestRemoveJobs:
    """Tests for remove_jobs function."""

    def test_remove_single_job(self, temp_data_dir):
        """Remove one job from results."""
        tmp_path, results_file, _ = temp_data_dir

        # Setup: create results with 3 jobs
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test"),
                Job(job_id="job_002", title="Job 2", company="Co2", url="http://2", source="test"),
                Job(job_id="job_003", title="Job 3", company="Co3", url="http://3", source="test"),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            removed, not_found = remove_jobs(["job_002"])

        assert removed == 1
        assert not_found == []
        data = json.loads(results_file.read_text())
        assert len(data["jobs"]) == 2
        assert all(j["job_id"] != "job_002" for j in data["jobs"])

    def test_remove_multiple_jobs(self, temp_data_dir):
        """Remove multiple jobs at once."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test"),
                Job(job_id="job_002", title="Job 2", company="Co2", url="http://2", source="test"),
                Job(job_id="job_003", title="Job 3", company="Co3", url="http://3", source="test"),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            removed, not_found = remove_jobs(["job_001", "job_003"])

        assert removed == 2
        assert not_found == []
        data = json.loads(results_file.read_text())
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "job_002"

    def test_remove_nonexistent_job(self, temp_data_dir):
        """Removing nonexistent job returns 0."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test")],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            removed, not_found = remove_jobs(["nonexistent"])

        assert removed == 0
        assert not_found == ["nonexistent"]


class TestUpdateJob:
    """Tests for update_job function."""

    def test_update_single_field(self, temp_data_dir):
        """Update one field of a job."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_001", title="Old Title", company="Co1", url="http://1", source="test"),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            updated = update_job("job_001", {"title": "New Title"})

        assert updated is not None
        assert updated.title == "New Title"
        assert updated.company == "Co1"  # Unchanged

        # Verify persistence
        data = json.loads(results_file.read_text())
        assert data["jobs"][0]["title"] == "New Title"

    def test_update_multiple_fields(self, temp_data_dir):
        """Update multiple fields at once."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_001", title="PM", company="Old Co", url="http://1", source="test", salary=None),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            updated = update_job("job_001", {"company": "New Co", "salary": "150k-200k", "level": "staff"})

        assert updated is not None
        assert updated.company == "New Co"
        assert updated.salary == "150k-200k"
        assert updated.level == "staff"
        assert updated.title == "PM"  # Unchanged

    def test_update_nonexistent_job(self, temp_data_dir):
        """Updating nonexistent job returns None."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test")],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            updated = update_job("nonexistent", {"title": "New Title"})

        assert updated is None

    def test_cannot_change_id(self, temp_data_dir):
        """Job ID cannot be changed via update."""
        tmp_path, results_file, _ = temp_data_dir

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test")],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            updated = update_job("job_001", {"id": "job_999", "title": "Updated"})

        assert updated is not None
        assert updated.job_id == "job_001"  # ID unchanged
        assert updated.title == "Updated"


class TestRemoveDeepDives:
    """Tests for remove_deep_dives function."""

    def test_remove_deep_dive(self, temp_data_dir):
        """Remove deep dive for a job."""
        tmp_path, results_file, deep_dives_file = temp_data_dir

        # Setup matching jobs (required since get_deep_dives prunes orphans)
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test"),
                Job(job_id="job_002", title="Job 2", company="Co2", url="http://2", source="test"),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        dives = DeepDives(
            deep_dives=[
                DeepDive(job_id="job_001", status="complete"),
                DeepDive(job_id="job_002", status="complete"),
            ]
        )
        deep_dives_file.write_text(json.dumps(dives.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.DEEP_DIVES_FILE", deep_dives_file):
                removed = remove_deep_dives(["job_001"])

        assert removed == 1
        data = json.loads(deep_dives_file.read_text())
        assert len(data["deep_dives"]) == 1
        assert data["deep_dives"][0]["job_id"] == "job_002"


class TestGetDeepDives:
    """Tests for get_deep_dives - pure read, no pruning."""

    def test_returns_all_deep_dives_including_orphans(self, temp_data_dir):
        """get_deep_dives returns all records without pruning orphans."""
        tmp_path, results_file, deep_dives_file = temp_data_dir

        # Job list has only job_002
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(job_id="job_002", title="Job 2", company="Co2", url="http://2", source="test"),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        # Deep dives include orphaned job_001
        dives = DeepDives(
            deep_dives=[
                DeepDive(job_id="job_001", status="complete"),
                DeepDive(job_id="job_002", status="complete"),
            ]
        )
        deep_dives_file.write_text(json.dumps(dives.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.DEEP_DIVES_FILE", deep_dives_file):
                result = get_deep_dives()

        # Both should be returned - no pruning
        assert len(result.deep_dives) == 2
        # File should NOT be modified
        data = json.loads(deep_dives_file.read_text())
        assert len(data["deep_dives"]) == 2


class TestSaveDeepDive:
    """Tests for save_deep_dive with job validation."""

    def test_save_deep_dive_for_existing_job(self, temp_data_dir):
        """Can save deep dive when job exists."""
        tmp_path, results_file, deep_dives_file = temp_data_dir

        # Setup: job exists
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[Job(job_id="job_001", title="Job 1", company="Co1", url="http://1", source="test")],
        )
        results_file.write_text(json.dumps(results.model_dump()))
        deep_dives_file.write_text(json.dumps({"deep_dives": []}))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.DEEP_DIVES_FILE", deep_dives_file):
                # Should not raise
                save_deep_dive(DeepDive(job_id="job_001", status="complete"))

        # Verify saved
        data = json.loads(deep_dives_file.read_text())
        assert len(data["deep_dives"]) == 1
        assert data["deep_dives"][0]["job_id"] == "job_001"

    def test_save_deep_dive_for_nonexistent_job_raises(self, temp_data_dir):
        """Saving deep dive for non-existent job raises JobNotFoundError."""
        tmp_path, results_file, deep_dives_file = temp_data_dir

        # Setup: no jobs
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[],
        )
        results_file.write_text(json.dumps(results.model_dump()))
        deep_dives_file.write_text(json.dumps({"deep_dives": []}))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.DEEP_DIVES_FILE", deep_dives_file):
                with pytest.raises(JobNotFoundError) as exc_info:
                    save_deep_dive(DeepDive(job_id="nonexistent", status="complete"))

        assert "nonexistent" in str(exc_info.value)
        # File should NOT be modified
        data = json.loads(deep_dives_file.read_text())
        assert len(data["deep_dives"]) == 0


class TestGetSelections:
    """Tests for get_selections with orphan pruning."""

    def test_prunes_orphaned_selections(self, temp_data_dir):
        """Selections for non-existent jobs are pruned."""
        tmp_path, results_file, _ = temp_data_dir
        selections_file = tmp_path / "selections.json"

        # Job list has only job_002
        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(
                    job_id="job_002",
                    title="Job 2",
                    company="Co2",
                    url="http://2",
                    source="test",
                ),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        # Selections include orphaned job_001
        selections = Selections(selected_ids=["job_001", "job_002"])
        selections_file.write_text(json.dumps(selections.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.SELECTIONS_FILE", selections_file):
                result = get_selections()

        # Only job_002 should remain
        assert result.selected_ids == ["job_002"]
        # File should be updated
        data = json.loads(selections_file.read_text())
        assert data["selected_ids"] == ["job_002"]

    def test_no_prune_when_all_valid(self, temp_data_dir):
        """No file write when all selections are valid."""
        tmp_path, results_file, _ = temp_data_dir
        selections_file = tmp_path / "selections.json"

        results = SearchResults(
            search_params=SearchParams(query="test"),
            jobs=[
                Job(
                    job_id="job_001",
                    title="Job 1",
                    company="Co1",
                    url="http://1",
                    source="test",
                ),
            ],
        )
        results_file.write_text(json.dumps(results.model_dump()))

        selections = Selections(selected_ids=["job_001"])
        selections_file.write_text(json.dumps(selections.model_dump()))

        with patch("server.data.RESULTS_FILE", results_file):
            with patch("server.data.SELECTIONS_FILE", selections_file):
                result = get_selections()

        assert result.selected_ids == ["job_001"]
