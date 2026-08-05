"""Add folder uniqueness and lookup indexes

Adds the unique constraint that makes lazy root-folder creation race safe,
plus the indexes the browse queries rely on. The GiST index on folders.path
is what makes future ltree subtree queries (@>, <@) usable.

If an existing database already contains duplicate (owner_id, path) rows from
before this constraint, resolve them by hand before running this migration;
the constraint creation will fail loudly rather than discard data.

Revision ID: b3d1f4c27a58
Revises: a17c8d9e0f12
Create Date: 2026-08-05 12:40:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b3d1f4c27a58"
down_revision = "a17c8d9e0f12"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_folders_owner_path", "folders", ["owner_id", "path"]
    )
    op.create_index("ix_folders_owner_parent", "folders", ["owner_id", "parent_id"])
    op.create_index(
        "ix_folders_path_gist", "folders", ["path"], postgresql_using="gist"
    )
    op.create_index("ix_files_owner_folder", "files", ["owner_id", "folder_id"])


def downgrade():
    op.drop_index("ix_files_owner_folder", table_name="files")
    op.drop_index("ix_folders_path_gist", table_name="folders")
    op.drop_index("ix_folders_owner_parent", table_name="folders")
    op.drop_constraint("uq_folders_owner_path", "folders", type_="unique")
