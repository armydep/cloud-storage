"""Add created_at timestamp to files table

Revision ID: d7g8h9i0j1k2
Revises: c6f7a8b9d0e1
Create Date: 2026-08-08 00:00:00.000000

"""
from alembic import op
from sqlalchemy import text


revision = "d7g8h9i0j1k2"
down_revision = "c6f7a8b9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE files
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_files_created_at ON files(created_at)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_files_created_at")
    op.execute("ALTER TABLE files DROP COLUMN IF EXISTS created_at")
