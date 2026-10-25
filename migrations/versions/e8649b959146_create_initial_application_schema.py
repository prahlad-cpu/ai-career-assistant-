"""Create the initial application schema.

Revision ID: e8649b959146
Revises:
Create Date: 2026-10-25 13:29:41.497616
"""

from alembic import op
import sqlalchemy as sa


revision = "e8649b959146"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Existing pre-migration databases already contain these tables.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "internships" not in existing_tables:
        op.create_table(
            "internships",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("company", sa.String(length=160), nullable=False),
            sa.Column("location", sa.String(length=100), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("stipend", sa.Integer(), nullable=False),
            sa.Column("duration", sa.String(length=80), nullable=False),
            sa.Column("domain", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("required_skills", sa.JSON(), nullable=False),
            sa.Column("preferred_skills", sa.JSON(), nullable=False),
            sa.Column("min_education", sa.String(length=80), nullable=False),
            sa.Column("posted_date", sa.Date(), nullable=False),
            sa.Column("apply_url", sa.String(length=500), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=True),
            sa.Column("embedding_backend", sa.String(length=80), nullable=True),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("company", "domain", "location", "mode", "title"):
            op.create_index(f"ix_internships_{column}", "internships", [column])

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("password_hash", sa.String(length=256), nullable=False),
            sa.Column("college", sa.String(length=160), nullable=True),
            sa.Column("degree", sa.String(length=120), nullable=True),
            sa.Column("branch", sa.String(length=120), nullable=True),
            sa.Column("graduation_year", sa.Integer(), nullable=True),
            sa.Column("preferred_locations", sa.JSON(), nullable=False),
            sa.Column("preferred_domains", sa.JSON(), nullable=False),
            sa.Column("internship_type", sa.String(length=20), nullable=True),
            sa.Column("minimum_stipend", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "resumes" not in existing_tables:
        op.create_table(
            "resumes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("parsed_text", sa.Text(), nullable=True),
            sa.Column("profile_json", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_resumes_user_id", "resumes", ["user_id"])

    if "match_scores" not in existing_tables:
        op.create_table(
            "match_scores",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("resume_id", sa.Integer(), nullable=False),
            sa.Column("internship_id", sa.String(length=80), nullable=False),
            sa.Column("resume_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("internship_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("final_score", sa.Float(), nullable=False),
            sa.Column("breakdown", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["internship_id"], ["internships.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("resume_id", "internship_id", name="uq_match_resume_internship"),
        )
        op.create_index("ix_match_scores_internship_id", "match_scores", ["internship_id"])
        op.create_index("ix_match_scores_resume_id", "match_scores", ["resume_id"])


def downgrade():
    op.drop_table("match_scores")
    op.drop_table("resumes")
    op.drop_table("users")
    op.drop_table("internships")
