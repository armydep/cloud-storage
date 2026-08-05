"""Rebuild files with ltree materialized paths

Revision ID: a17c8d9e0f12
Revises: f0b7a8c9d1e2
Create Date: 2026-08-05 03:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a17c8d9e0f12"
down_revision = "f0b7a8c9d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")
    op.execute("DROP TABLE IF EXISTS user_path_contents")
    op.execute("DROP TABLE IF EXISTS user_paths")
    op.execute(
        """
        CREATE TABLE folders (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
            path LTREE NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE files (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            folder_id UUID NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            category TEXT NOT NULL,
            blob_hash TEXT NOT NULL,
            size_bytes BIGINT NOT NULL
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS files")
    op.execute("DROP TABLE IF EXISTS folders")
    op.execute(
        """
        CREATE TABLE user_paths (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            folder_path VARCHAR(1024) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT uq_user_paths_user_folder_path UNIQUE (user_id, folder_path)
        )
        """
    )
    op.execute("CREATE INDEX ix_user_paths_user_id ON user_paths (user_id)")
    op.execute(
        """
        CREATE INDEX ix_user_paths_user_id_folder_path
        ON user_paths (user_id, folder_path)
        """
    )
    op.execute(
        """
        CREATE TABLE user_path_contents (
            id UUID PRIMARY KEY,
            user_path_id UUID NOT NULL REFERENCES user_paths(id) ON DELETE CASCADE,
            s3_path VARCHAR(2048) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE,
            file_type VARCHAR(64) NOT NULL
        )
        """
    )
