8. How to work (process rules for the agent(s))

If you are one agent, work through the phases in order. If multiple agents are available, split them like this and sync via the shared interfaces defined in app/services/*/base.py:

Agent A, Backend/Infra: app factory, models, migrations, auth, upload flow, config, security, Docker, deployment.
Agent B, NLP/ML: parser, section detector, skill taxonomy and extractor, embeddings, matching engine, ATS scorer, skill-gap, evaluation script.
Agent C, LLM/Tailoring: LLM adapters, prompts, JSON schemas, guardrails, tailoring service, DOCX export.
Agent D, Frontend/UX + QA: templates, UI, dark mode, accessibility, tests, README, demo data.

Phases

Scaffold the repo, config, DB models, auth, and a working "hello dashboard". Verify the app boots.
Resume upload, parsing, section detection, skill extraction, and the analysis page. Add unit tests with fixture resumes.
Internship data layer, seed data, embedding precompute, and the matching engine. Add the recommendations UI.
Skill-gap analysis and ATS scoring UI.
LLM service, tailoring, guardrails, and DOCX export.
Tracker, paste-a-JD, profile and settings, and polish (empty states, errors, dark mode).
Evaluation script, tests, security review, Dockerfile, and deploy config.
README and docs. A final end-to-end verification.

Rules

Do not leave TODOs, stubs, lorem ipsum or fake "coming soon" buttons. If something is out of scope, remove it from the UI.
After each phase, actually run the app and tests, fix failures, and only then proceed. Do not claim something works without running it.
Prefer boring, well-known libraries. Pin versions. Keep dependencies minimal to stay within the memory budget.
When a requirement is ambiguous, choose the simplest reasonable option, note it in docs/decisions.md, and keep moving. Do not block on questions.
Commit in small logical commits with clear messages (if git is available).
Never hardcode API keys. Never log resume contents.
9. Acceptance criteria (the project is "done" only when all are true)
 docker build and docker run start the app, and /healthz returns 200.
 A new user can register, upload a sample PDF resume, and see a parsed profile with correctly extracted skills within about 10 seconds.
 The ATS score and the breakdown checklist display correctly.
 The recommendations page shows ranked internships with sub-scores, matched and missing skills, and a readable reason for each.
 Filters, sorting, and search on recommendations work.
 Skill-gap view works for any internship and for a pasted JD.
 Tailoring produces keyword suggestions and bullet rewrites with a diff, flags any new skill not in the original resume, and exports a valid DOCX that opens in Word.
 With no LLM key set, the whole app still works (rule-based fallback and a visible notice).
 Another user cannot access my resume or data (tested).
 pytest passes, with at least 25 meaningful tests covering the parser, extractor, matching, authorization and tailoring guardrails.
 scripts/evaluate_matching.py runs and prints the metrics table.
 The app runs within 512 MB RAM under light use.
 README includes: overview, screenshots (or a screenshot-generation script), architecture diagram (Mermaid), setup, env var table, deployment guide, evaluation results, limitations and future work.
 The app is deployed to a public URL, or render.yaml is verified to deploy without manual fixes.