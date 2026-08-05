"""Add file storage constraints

Revision ID: b4c7d8e9f012
Revises: a17c8d9e0f12
Create Date: 2026-08-05 20:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b4c7d8e9f012"
down_revision = "a17c8d9e0f12"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS ix_files_owner_id ON files(owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_files_folder_id ON files(folder_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_files_blob_hash ON files(blob_hash)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_files_folder_name
        ON files(folder_id, name)
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_folders_owner_id ON folders(owner_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_folders_owner_path
        ON folders(owner_id, path)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_folders_parent_name
        ON folders(parent_id, name)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_folders_path_gist
        ON folders USING GIST(path)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_folders_path_gist")
    op.execute("DROP INDEX IF EXISTS uq_folders_parent_name")
    op.execute("DROP INDEX IF EXISTS uq_folders_owner_path")
    op.execute("DROP INDEX IF EXISTS ix_folders_owner_id")
    op.execute("DROP INDEX IF EXISTS uq_files_folder_name")
    op.execute("DROP INDEX IF EXISTS ix_files_blob_hash")
    op.execute("DROP INDEX IF EXISTS ix_files_folder_id")
    op.execute("DROP INDEX IF EXISTS ix_files_owner_id")
