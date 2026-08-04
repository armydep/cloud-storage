"""Add file entries

Revision ID: 6f9f6e91d0a1
Revises: fe56fa70289e
Create Date: 2026-08-05 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "6f9f6e91d0a1"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fileentry",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["fileentry.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fileentry_owner_root",
        "fileentry",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND type = 'folder'"),
    )


def downgrade():
    op.drop_index("ix_fileentry_owner_root", table_name="fileentry")
    op.drop_table("fileentry")
