"""Rebuild file storage tables

Revision ID: f0b7a8c9d1e2
Revises: 6f9f6e91d0a1
Create Date: 2026-08-05 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f0b7a8c9d1e2"
down_revision = "6f9f6e91d0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_fileentry_owner_root", table_name="fileentry")
    op.drop_table("fileentry")

    op.create_table(
        "user_paths",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "folder_path", name="uq_user_paths_user_folder_path"
        ),
    )
    op.create_index("ix_user_paths_user_id", "user_paths", ["user_id"])
    op.create_index(
        "ix_user_paths_user_id_folder_path",
        "user_paths",
        ["user_id", "folder_path"],
    )

    op.create_table(
        "user_path_contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_path_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("s3_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_path_id"], ["user_paths.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("user_path_contents")
    op.drop_index("ix_user_paths_user_id_folder_path", table_name="user_paths")
    op.drop_index("ix_user_paths_user_id", table_name="user_paths")
    op.drop_table("user_paths")

    op.create_table(
        "fileentry",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
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
