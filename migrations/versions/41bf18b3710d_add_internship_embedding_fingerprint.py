"""Add the internship embedding content fingerprint.

Revision ID: 41bf18b3710d
Revises: e8649b959146
Create Date: 2026-10-25 13:34:00
"""

from alembic import op
import sqlalchemy as sa


revision = "41bf18b3710d"
down_revision = "e8649b959146"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("internships")
    }
    if "embedding_fingerprint" not in columns:
        op.add_column(
            "internships",
            sa.Column("embedding_fingerprint", sa.String(length=64), nullable=True),
        )


def downgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("internships")
    }
    if "embedding_fingerprint" in columns:
        op.drop_column("internships", "embedding_fingerprint")
