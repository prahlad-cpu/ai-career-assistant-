# AI Career Assistant

Phase 1 delivers the Flask application foundation: account registration and
login, a student profile with internship preferences, and an authenticated
dashboard. Resume analysis and internship matching are intentionally not part
of this phase.

## Run locally

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app wsgi run --debug
```

Open <http://127.0.0.1:5000>. The first launch creates a local SQLite database
in Flask's instance directory. The app can also be started with `python wsgi.py`.

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

## Project status

The implementation follows the phases in [agent_build_prompt.md](./agent_build_prompt.md).
Current architectural choices are recorded in [docs/decisions.md](./docs/decisions.md).
