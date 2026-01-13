"""Tests for applications data layer."""

import shutil

import pytest

from server.applications import (
    APPLICATIONS_DIR,
    GapAnalysis,
    InterviewPrep,
    JobSummary,
    WhatToSayItem,
    create_application,
    delete_application,
    get_application,
    list_applications,
    save_cv_tailored,
    save_gap_analysis,
    save_interview_prep,
    save_jd,
    update_application_status,
)


@pytest.fixture
def test_job():
    """Create a test job summary."""
    return JobSummary(
        job_id="job_test123",
        title="Senior Product Manager",
        company="Test Corp",
        url="https://example.com/job/123",
        location="Remote",
        posted="2025-01-01",
    )


@pytest.fixture
def cleanup_test_apps():
    """Clean up test applications after tests."""
    created_apps = []
    yield created_apps
    for app_id in created_apps:
        app_dir = APPLICATIONS_DIR / app_id
        if app_dir.exists():
            shutil.rmtree(app_dir)


class TestCreateApplication:
    def test_creates_directory(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        assert app.application_id.endswith("-test-corp-senior-product-manager")
        assert app.status == "pending"
        assert app.job.job_id == "job_test123"

        app_dir = APPLICATIONS_DIR / app.application_id
        assert app_dir.exists()
        assert (app_dir / "metadata.json").exists()

    def test_handles_duplicate_ids(self, test_job, cleanup_test_apps):
        app1 = create_application(test_job)
        cleanup_test_apps.append(app1.application_id)

        app2 = create_application(test_job)
        cleanup_test_apps.append(app2.application_id)

        assert app1.application_id != app2.application_id
        assert app2.application_id.endswith("-1")


class TestGetApplication:
    def test_returns_none_for_nonexistent(self):
        result = get_application("nonexistent-app-id")
        assert result is None

    def test_loads_full_application(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        # Save some data
        save_jd(app.application_id, "# Job Description\n\nTest content")
        save_gap_analysis(app.application_id, GapAnalysis(
            matches=["Python: 5 years exp"],
            partial_matches=["ML: Some exposure"],
            gaps=[],
        ))

        loaded = get_application(app.application_id)
        assert loaded is not None
        assert loaded.jd == "# Job Description\n\nTest content"
        assert len(loaded.gap_analysis.matches) == 1
        assert "Python" in loaded.gap_analysis.matches[0]


class TestListApplications:
    def test_lists_all_applications(self, test_job, cleanup_test_apps):
        app1 = create_application(test_job)
        cleanup_test_apps.append(app1.application_id)

        test_job2 = JobSummary(
            job_id="job_test456",
            title="Staff Engineer",
            company="Another Co",
            url="https://example.com/job/456",
        )
        app2 = create_application(test_job2)
        cleanup_test_apps.append(app2.application_id)

        apps = list_applications()
        app_ids = [a.application_id for a in apps]

        assert app1.application_id in app_ids
        assert app2.application_id in app_ids


class TestDeleteApplication:
    def test_deletes_application(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        app_dir = APPLICATIONS_DIR / app.application_id

        assert app_dir.exists()
        result = delete_application(app.application_id)
        assert result is True
        assert not app_dir.exists()

    def test_returns_false_for_nonexistent(self):
        result = delete_application("nonexistent-app-id")
        assert result is False


class TestUpdateStatus:
    def test_updates_status(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        update_application_status(app.application_id, "complete")
        loaded = get_application(app.application_id)
        assert loaded.status == "complete"

    def test_updates_error(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        update_application_status(app.application_id, "error", "Scraping failed")
        loaded = get_application(app.application_id)
        assert loaded.status == "error"


class TestSaveContent:
    def test_save_jd(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        save_jd(app.application_id, "# Test JD")
        loaded = get_application(app.application_id)
        assert loaded.jd == "# Test JD"

    def test_save_interview_prep(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        prep = InterviewPrep(
            what_to_say=[WhatToSayItem(question="Tell me about AI work", answer="Shipped AI feature")],
            questions_to_ask=["What's the team size?"],
            red_flags=["Early stage startup"],
        )
        save_interview_prep(app.application_id, prep)

        loaded = get_application(app.application_id)
        assert len(loaded.interview_prep.what_to_say) == 1
        assert loaded.interview_prep.questions_to_ask[0] == "What's the team size?"

    def test_cv_versioning(self, test_job, cleanup_test_apps):
        app = create_application(test_job)
        cleanup_test_apps.append(app.application_id)

        # Save first version
        save_cv_tailored(app.application_id, "# CV v1")

        # Save second version (should version the first)
        save_cv_tailored(app.application_id, "# CV v2")

        loaded = get_application(app.application_id)
        assert loaded.cv_tailored == "# CV v2"

        # Check versioned file exists
        app_dir = APPLICATIONS_DIR / app.application_id
        assert (app_dir / "cv-tailored.v1.md").exists()
        assert (app_dir / "cv-tailored.v1.md").read_text() == "# CV v1"
