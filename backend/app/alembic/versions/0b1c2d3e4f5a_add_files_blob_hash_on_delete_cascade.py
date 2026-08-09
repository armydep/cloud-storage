"""Add ON DELETE CASCADE to files blob hash foreign key

Revision ID: 0b1c2d3e4f5a
Revises: f1a2b3c4d5e6
Create Date: 2026-08-09 00:00:00.000000

"""

from alembic import op

revision = "0b1c2d3e4f5a"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE files
        DROP CONSTRAINT IF EXISTS fk_files_blob_hash_file_blobs
        """
    )
    op.execute(
        """
        ALTER TABLE files
        ADD CONSTRAINT fk_files_blob_hash_file_blobs
        FOREIGN KEY (blob_hash)
        REFERENCES file_blobs(blob_hash)
        ON UPDATE CASCADE
        ON DELETE CASCADE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE files
        DROP CONSTRAINT IF EXISTS fk_files_blob_hash_file_blobs
        """
    )
    op.execute(
        """
        ALTER TABLE files
        ADD CONSTRAINT fk_files_blob_hash_file_blobs
        FOREIGN KEY (blob_hash)
        REFERENCES file_blobs(blob_hash)
        ON UPDATE CASCADE
        """
    )
