# AI Career Assistant

Phase 3 delivers the Flask application foundation, resume analysis, and
internship recommendations:
account registration and login, a student profile, an authenticated dashboard,
private PDF/DOCX uploads, rule-based section and skill extraction, and a
structured profile view. A curated 91-listing internship dataset powers ranked
recommendations with match explanations and filters. ATS scoring is left for a
later phase.

## Run locally

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app wsgi db upgrade
python -m flask --app wsgi seed-internships
python -m flask --app wsgi run --debug
```

Open <http://127.0.0.1:5000>. Register, then choose **Resumes** to upload a
PDF or DOCX (maximum 5 MB). Scanned/image-only PDFs are rejected because they
do not contain selectable text. The original upload is deleted once parsing
finishes; the normalized text and extracted profile are stored in the database.
The migration creates a local SQLite database in Flask's instance directory.
Edit `.env` to override local settings. The app can also be started with
`python wsgi.py` after applying migrations.
The seed command precomputes and stores internship vectors using
`BAAI/bge-small-en-v1.5` through FastEmbed. If the model cannot be loaded,
the app logs the unavailable backend and uses deterministic local embeddings
so matching remains usable.

## Tests

```powershell
python -m pytest
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_ENV` | Configuration profile: `development`, `testing`, or `production` | `development` |
| `SECRET_KEY` | Signs sessions and CSRF tokens; set a strong random value for deployment | Local development key |
| `DATABASE_URL` | SQLAlchemy database URI | Local SQLite database |
| `EMBEDDING_MODEL` | FastEmbed model used for recommendation vectors | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_CACHE_DIR` | Optional directory for the downloaded FastEmbed model cache | FastEmbed default cache |

Production requires `SECRET_KEY` to be set before deployment. Secure session
cookies are enabled in the production configuration.

## Database migrations

The application does not create or modify tables at startup. Apply committed
migrations before seeding data or running the app. For a fresh clone on Windows,
run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app wsgi db upgrade
python -m flask --app wsgi seed-internships
python -m flask --app wsgi run --debug
```

For every model/schema change, generate and review a migration, then apply it:

```powershell
python -m flask --app wsgi db migrate -m "Describe the schema change"
python -m flask --app wsgi db upgrade
```

Commit the generated file under `migrations/versions/` with the model change.
Existing databases created before migrations are adopted by the initial
baseline revision; subsequent revisions apply missing schema changes without
recreating their existing tables.

## Resume parsing

The parser uses `pdfplumber` for selectable PDF text and `python-docx` for
Word documents. A curated JSON taxonomy contains 300+ canonical skills and
aliases; detected skills are grouped by category. Users can keep several
resumes and choose which profile is active. Resume analysis routes are scoped
to the signed-in user.

## Internship matching

The original, synthetic internship listings are in
[`data/internships_seed.json`](./data/internships_seed.json). Reload them and
precompute vectors with `python -m flask --app wsgi seed-internships`.
Recommendation weights are maintained in [`config/matching.yaml`](./config/matching.yaml):

| Component | Weight |
| --- | ---: |
| Semantic similarity | 0.50 |
| Required/preferred skill overlap | 0.30 |
| Education and project/experience fit | 0.10 |
| Location, mode, stipend, and domain preferences | 0.10 |

The **Recommendations** page supports search, domain/location/mode filters,
minimum stipend and score thresholds, sorting, pagination, matched and missing
skills, and per-component scores. The scoring selector also exposes a
keyword-only TF-IDF cosine baseline. Scores are cached per resume/listing and
recomputed when either record changes. If a BGE model install is not supported
by the local Python runtime, the same CLI and web flow use a deterministic,
CPU-only feature-hash fallback; for the project-specified Python 3.11 runtime,
FastEmbed is installed from the pinned requirements.

## ATS and skill-gap analysis

Resume analysis includes a rule-based 0–100 ATS compatibility score, a weighted
checklist, and up to five prioritized fixes. Select an internship to include
its skills in the keyword coverage check. ATS formatting checks use extracted
text only; the original upload is deleted after parsing, so columns and images
cannot be inspected. This score is a transparent heuristic, not a guarantee
from any employer's ATS.

Open a recommendation's skill-gap view to see exact, partial, and missing
skills, a weighted readiness gauge, and a priority-ordered learning plan.
Partial matches use taxonomy aliases and conservative similarity heuristics;
confirm them against your actual experience. The pasted-JD analyzer extracts
known taxonomy skills and keeps the submitted text only for the current
response—it is not stored in the database.

## Project status

The implementation follows the phases in [agent_build_prompt.md](./agent_build_prompt.md).
Current architectural choices are recorded in [docs/decisions.md](./docs/decisions.md).
