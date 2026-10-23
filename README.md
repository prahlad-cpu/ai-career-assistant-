# AI Career Assistant

Phase 2 delivers the Flask application foundation and resume analysis:
account registration and login, a student profile, an authenticated dashboard,
private PDF/DOCX uploads, rule-based section and skill extraction, and a
structured profile view. Internship matching and ATS scoring are intentionally
left for later phases.

## Run locally

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app wsgi run --debug
```

Open <http://127.0.0.1:5000>. Register, then choose **Resumes** to upload a
PDF or DOCX (maximum 5 MB). Scanned/image-only PDFs are rejected because they
do not contain selectable text. The original upload is deleted once parsing
finishes; the normalized text and extracted profile are stored in the database.
The first launch creates a local SQLite database in Flask's instance directory.
Edit `.env` to override local settings. The app can also be started with
`python wsgi.py` when environment variables are already configured.

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

Production requires `SECRET_KEY` to be set before deployment. Secure session
cookies are enabled in the production configuration.

## Resume parsing

The parser uses `pdfplumber` for selectable PDF text and `python-docx` for
Word documents. A curated JSON taxonomy contains 300+ canonical skills and
aliases; detected skills are grouped by category. Users can keep several
resumes and choose which profile is active. Resume analysis routes are scoped
to the signed-in user.

## Project status

The implementation follows the phases in [agent_build_prompt.md](./agent_build_prompt.md).
Current architectural choices are recorded in [docs/decisions.md](./docs/decisions.md).
