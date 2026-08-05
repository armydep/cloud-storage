"""Add composite owner indexes for folder and file listing

Revision b4c7d8e9f012 indexes owner_id and parent_id/folder_id separately.
The browse endpoint filters on both columns together
(WHERE owner_id = ? AND parent_id/folder_id = ?), so give it composite
indexes to match rather than relying on the planner combining two single
-column indexes.

Revision ID: b5e2a91c7f34
Revises: b4c7d8e9f012
Create Date: 2026-08-05 21:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b5e2a91c7f34"
down_revision = "b4c7d8e9f012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_folders_owner_parent "
        "ON folders(owner_id, parent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_files_owner_folder "
        "ON files(owner_id, folder_id)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_files_owner_folder")
    op.execute("DROP INDEX IF EXISTS ix_folders_owner_parent")
