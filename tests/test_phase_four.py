"""ATS scoring and role-specific skill-gap analysis tests."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.extensions import db
from app.models import Internship, Resume, User
from app.services.ats_scorer import score_resume
from app.services.skill_gap import analyze_skill_gap, extract_job_skill_requirements


def test_ats_report_has_weighted_checklist_and_prioritized_fixes():
    resume = SimpleNamespace(
        profile_json={
            "email": "student@example.com",
            "phone": "+91 98765 43210",
            "links": {"github": ["github.com/student"]},
            "sections": ["education", "skills", "projects"],
            "skills": {"Programming Languages": ["Python", "React"]},
            "education": ["B.Tech Computer Science"],
            "projects": ["Built a student portfolio website."],
        },
        parsed_text="Python React built a student portfolio.",
    )

    report = score_resume(resume, target_skills=["Python", "SQL"], target_title="Data Intern")

    assert 0 <= report.score <= 100
    assert sum(check.weight for check in report.checks) == 100
    assert {check.label for check in report.checks} == {
        "Contact information",
        "Standard sections",
        "Skills and target keywords",
        "Action verbs and quantified impact",
        "Length and bullet density",
        "Text-based formatting checks",
    }
    assert "1 of 2 target skills found" in next(
        check.detail for check in report.checks if check.label == "Skills and target keywords"
    )
    assert 1 <= len(report.top_fixes) <= 5
    assert report.target_title == "Data Intern"


def test_ats_report_handles_empty_resume_without_invalid_scores():
    resume = SimpleNamespace(profile_json=None, parsed_text=None)

    report = score_resume(resume)

    assert report.score == 0
    assert len(report.top_fixes) == 5
    assert all(0 <= check.score <= 100 for check in report.checks)
    assert report.target_title is None


def test_skill_gap_classifies_exact_partial_and_missing_skills_and_prioritizes():
    report = analyze_skill_gap(
        {"skills": {"Programming Languages": ["Python"], "Frontend Development": ["React"]}},
        required_skills=["Python", "React Native", "Kubernetes"],
        preferred_skills=["Docker"],
    )
    states = {item.name: item.status for item in report.assessments}

    assert states == {
        "Python": "matched",
        "React Native": "partial",
        "Kubernetes": "missing",
        "Docker": "missing",
    }
    assert report.readiness == 43
    assert report.matched_count == 1
    assert report.partial_count == 1
    assert report.missing_count == 2
    assert report.learning_plan[0].name == "Kubernetes"
    assert report.learning_plan[0].priority == "High"
    assert len(report.learning_plan[0].resources) == 3
    assert all(url.startswith("https://") for _, url in report.learning_plan[0].resources)


def test_pasted_description_extracts_and_separates_required_and_preferred_skills():
    required, preferred = extract_job_skill_requirements(
        "Required skills: Python, SQL, PostgreSQL\nPreferred skills: Docker, Kubernetes"
    )

    assert {"Python", "SQL", "PostgreSQL"} <= set(required)
    assert {"Docker", "Kubernetes"} <= set(preferred)
    assert not set(required) & set(preferred)


def _create_account_resume_and_internship(app, email):
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == email))
        assert user is not None
        resume = Resume(
            user=user,
            original_filename="resume.docx",
            parsed_text="Python and React student portfolio project.",
            profile_json={
                "skills": {"Programming Languages": ["Python"], "Frontend Development": ["React"]},
                "projects": ["Built a portfolio using React."],
                "sections": ["skills", "projects"],
            },
            is_active=True,
        )
        internship = Internship(
            id="phase-four-test",
            title="Software Intern",
            company="Example Co",
            location="Remote",
            mode="remote",
            stipend=10000,
            duration="3 months",
            domain="Software Engineering",
            description="Use Python and React Native. Preferred: Docker.",
            required_skills=["Python", "React Native", "Kubernetes"],
            preferred_skills=["Docker"],
            min_education="Undergraduate",
            posted_date=date.today(),
            apply_url="#",
            source="test",
        )
        db.session.add_all([user, resume, internship])
        db.session.commit()
        return user.id, resume.id


def _register(client, email):
    response = client.post(
        "/register",
        data={
            "name": "Gap Student",
            "email": email,
            "password": "strong-password",
            "confirm_password": "strong-password",
        },
    )
    assert response.status_code == 302


def test_analysis_page_renders_ats_score_checklist_and_top_fixes(client, app):
    _register(client, "ats-ui@example.com")
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "ats-ui@example.com"))
        resume = Resume(
            user_id=user.id,
            original_filename="resume.docx",
            parsed_text="Python React built a student project.",
            profile_json={
                "email": "student@example.com",
                "skills": {"Programming Languages": ["Python", "React"]},
                "projects": ["Built a student project."],
                "sections": ["skills", "projects"],
            },
            is_active=True,
        )
        internship = Internship(
            id="ats-target-test",
            title="Data Analyst Intern",
            company="Example Co",
            location="Remote",
            mode="remote",
            stipend=10000,
            duration="3 months",
            domain="Data Analytics",
            description="Analyze data with Python and SQL.",
            required_skills=["Python", "SQL"],
            preferred_skills=[],
            min_education="Undergraduate",
            posted_date=date.today(),
            apply_url="#",
            source="test",
        )
        db.session.add_all([resume, internship])
        db.session.commit()
        resume_id = resume.id

    response = client.get(f"/resumes/{resume_id}")

    assert response.status_code == 200
    assert b"ATS compatibility" in response.data
    assert b"ATS checklist" in response.data
    assert b"Top 5 fixes" in response.data
    assert b"aria-valuenow=" in response.data

    targeted_response = client.get(
        f"/resumes/{resume_id}?internship_id=ats-target-test"
    )
    assert targeted_response.status_code == 200
    assert b"Keyword coverage is checked against Data Analyst Intern" in targeted_response.data
    assert b"1 of 2 target skills found" in targeted_response.data


def test_internship_skill_gap_page_uses_active_resume_and_shows_learning_plan(client, app):
    _register(client, "role-gap@example.com")
    _create_account_resume_and_internship(app, "role-gap@example.com")

    response = client.get("/skill-gap/phase-four-test")

    assert response.status_code == 200
    assert b"Role readiness" in response.data
    assert b"React Native" in response.data
    assert b"Related resume skill: React" in response.data
    assert b"Priority learning plan" in response.data
    assert b"Kubernetes" in response.data


def test_pasted_job_description_is_analyzed_without_creating_database_rows(client, app):
    _register(client, "pasted-gap@example.com")
    _create_account_resume_and_internship(app, "pasted-gap@example.com")
    with app.app_context():
        before = db.session.query(Internship).count()

    response = client.post(
        "/skill-gap/paste",
        data={
            "title": "Data Engineer Intern",
            "description": (
                "Required skills: Python, SQL, PostgreSQL\n"
                "Preferred skills: Docker, Kubernetes"
            ),
        },
    )

    assert response.status_code == 200
    assert b"Data Engineer Intern" in response.data
    assert b"Role readiness" in response.data
    assert b"PostgreSQL" in response.data
    assert b"Priority learning plan" in response.data
    with app.app_context():
        assert db.session.query(Internship).count() == before


def test_pasted_job_description_rejects_empty_input(client):
    _register(client, "empty-jd@example.com")

    response = client.post("/skill-gap/paste", data={"title": "", "description": " "})

    assert response.status_code == 200
    assert b"Paste a job description" in response.data


def test_skill_gap_requires_login_and_unknown_internship_is_not_found(client, app):
    assert app.test_client().get("/skill-gap/phase-four-test").status_code == 302
    _register(client, "missing-role@example.com")
    _create_account_resume_and_internship(app, "missing-role@example.com")
    assert client.get("/skill-gap/not-a-real-role").status_code == 404
