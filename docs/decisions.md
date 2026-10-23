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
