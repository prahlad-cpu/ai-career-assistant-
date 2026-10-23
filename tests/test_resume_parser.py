"""Resume extraction, normalization, and taxonomy tests."""

from pathlib import Path

from app.services.resume_parser import (
    ResumeParseError,
    normalize_resume_text,
    parse_resume_text,
)
from app.services.section_detector import detect_sections
from app.services.skill_extractor import canonicalize_skill, extract_skills, load_taxonomy


FIXTURES = Path(__file__).parent / "fixtures"


def test_normalization_rejoins_hyphenated_words_and_normalizes_bullets():
    result = normalize_resume_text("Pro\u00ad-\r\n  ject work\n•   Built an app")

    assert result == "Project work\n- Built an app"


def test_section_detector_recognizes_common_heading_variants():
    sections = detect_sections(
        "Sam Student\nPROFESSIONAL SUMMARY:\nBuilds useful tools.\n"
        "Technical Skills\nPython\nAcademic Projects:\nA class project"
    )

    assert sections == {
        "summary": "Builds useful tools.",
        "skills": "Python",
        "projects": "A class project",
    }


def test_parse_resume_extracts_contact_education_links_and_section_entries():
    source = (FIXTURES / "student_resume.txt").read_text(encoding="utf-8")

    parsed = parse_resume_text(source)

    assert parsed.profile["name"] == "Aarav Mehta"
    assert parsed.profile["email"] == "aarav.mehta@example.com"
    assert parsed.profile["phone"] == "+91 98765 43210"
    assert parsed.profile["links"] == {
        "linkedin": ["https://linkedin.com/in/aarav-mehta"],
        "github": ["https://github.com/aaravmehta"],
    }
    assert parsed.profile["education"] == ["B.Tech Computer Science, Northstar Institute, 2027"]
    assert parsed.profile["projects"] == [
        "Built a resume analyzer with Python and Flask.",
        "Developed a React dashboard backed by PostgreSQL.",
    ]
    assert "certifications" in parsed.profile["sections"]


def test_skill_extraction_canonicalizes_aliases_and_groups_categories():
    skills = extract_skills("Used py, JS, sklearn, nodejs, and AWS in a RAG project.")

    assert skills["Programming Languages"] == ["JavaScript", "Python"]
    assert skills["Data Science and Machine Learning"] == [
        "Retrieval-Augmented Generation",
        "scikit-learn",
    ]
    assert skills["Backend Development"] == ["Node.js"]
    assert skills["Cloud and DevOps"] == ["Amazon Web Services"]


def test_skill_match_does_not_accept_partial_word_matches():
    skills = extract_skills("I enjoy JavaScript and Flasky projects.")

    assert skills == {"Programming Languages": ["JavaScript"]}


def test_taxonomy_has_more_than_300_skills_and_valid_aliases():
    taxonomy = load_taxonomy()

    assert sum(len(skills) for skills in taxonomy["categories"].values()) >= 300
    assert canonicalize_skill("py") == "Python"
    assert canonicalize_skill("unknown-language") is None


def test_empty_or_whitespace_only_resume_text_is_rejected():
    try:
        parse_resume_text(" \n\t ")
    except ResumeParseError as error:
        assert "No readable text" in str(error)
    else:
        raise AssertionError("An empty resume must be rejected.")


def test_fixture_text_is_parseable():
    parsed = parse_resume_text((FIXTURES / "student_resume.txt").read_text(encoding="utf-8"))

    assert parsed.text.startswith("Aarav Mehta")
    assert "Docker" in parsed.profile["skills"]["Cloud and DevOps"]
