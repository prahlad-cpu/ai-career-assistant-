# Phase 1 decisions

- The application factory creates the SQLAlchemy tables on startup so a fresh
  local checkout can run immediately. Flask-Migrate is initialized for
  migration-managed schema changes in later phases; migrations will replace
  `create_all` once the schema begins evolving.
- Student locations and domains are stored as JSON string lists. This keeps
  profile preferences structured without adding a separate preference table.
- Phase 1 implements accounts, profile preferences, and the authenticated
  dashboard only. Resume upload and internship features are deliberately
  deferred to their specified later phases.

# Phase 2 decisions

- Resume source files are written under a UUID filename in a private upload
  directory and removed in a `finally` block after parsing, whether parsing
  succeeds or fails. Only the normalized text and structured profile remain
  in the database.
- PDF content must be selectable text. OCR is intentionally not included;
  image-only or scanned PDFs are rejected with a clear upload error.
- The taxonomy is a curated, repository-owned JSON list with 300+ skills,
  categories, and explicit common aliases. Extraction is deterministic and
  local so it works without an external API.
- The most recently uploaded resume becomes active. The resume list allows
  users to switch the active profile without deleting other versions.
- SQLAlchemy is pinned at 2.1.5: the installed development Python is 3.15, and
  the original 2.0.36 pin failed during model initialization there. The newer
  pin retains support for the specified Python 3.11 minimum.

# Phase 3 decisions

- The seed dataset is original, generated project data with 91 records across
  13 internship domains. The loader canonicalizes the supplied skill lists and
  unions taxonomy skills it finds in each listing description.
- The seed CLI upserts rows by stable ID, removes stale seed rows, and
  precomputes BGE embeddings. `--without-embeddings` is available for offline
  database setup; the recommendation service fills missing vectors on demand.
- FastEmbed is pinned for supported runtimes, with a Python 3.15 environment
  marker because ONNX Runtime currently has no compatible Windows wheel in the
  available interpreter. A deterministic hashed text-vector service keeps
  seeding and recommendations functional when FastEmbed or model downloads are
  unavailable.
- Matching uses separate resume skill, project, experience, and summary
  chunks, percentile-calibrated cosine similarity, taxonomy skill coverage,
  education/experience fit, and saved preferences. The exact blend is kept in
  `config/matching.yaml`. A dependency-light TF-IDF cosine baseline is available
  from the recommendations page for comparison.
- Matching weights are read from the small scalar-only YAML file with a
  focused parser rather than introducing a YAML runtime dependency for the app.
- Recommendation results are cached by resume/listing pair with content
  fingerprints, so profile, listing, and embedding-backend changes invalidate
  stale results without storing resume text in logs.
- Database schema changes are versioned with Flask-Migrate and Alembic; app
  startup no longer creates tables implicitly. The first baseline skips tables
  already present in pre-migration local databases, and the follow-up revision
  adds `internships.embedding_fingerprint`.

# Phase 4 decisions

- ATS scoring is a deterministic, weighted checklist computed from the parsed
  resume profile and normalized text. Target skills from an optional selected
  internship contribute to the skills/keyword check. The UI describes the
  result as a heuristic and explicitly notes that original document layout is
  unavailable after private upload files are deleted.
- Skill-gap analysis uses the existing curated taxonomy for exact/alias matches,
  with conservative name/category overlap for partial matches. Readiness counts
  partial skills as half credit and weights required skills twice as much as
  preferred skills. Learning links are search queries rather than guessed
  course or documentation URLs.
- Pasted job descriptions are bounded to 12,000 characters, CSRF protected, and
  analyzed in the request without persisting the text or adding database models.
