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
