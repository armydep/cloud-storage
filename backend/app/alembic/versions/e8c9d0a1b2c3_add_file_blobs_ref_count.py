"""Add file blob ref counts

Revision ID: e8c9d0a1b2c3
Revises: d7g8h9i0j1k2
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op


revision = "e8c9d0a1b2c3"
down_revision = "d7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM files
                GROUP BY blob_hash
                HAVING COUNT(DISTINCT size_bytes) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot backfill file_blobs: same blob_hash has multiple sizes';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_blobs (
            blob_hash TEXT PRIMARY KEY,
            object_key TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            ref_count INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_file_blobs_object_key UNIQUE (object_key),
            CONSTRAINT ck_file_blobs_ref_count_non_negative CHECK (ref_count >= 0)
        )
        """
    )
    op.execute(
        """
        INSERT INTO file_blobs (blob_hash, object_key, size_bytes, ref_count)
        SELECT
            blob_hash,
            'sha256/' || blob_hash,
            MIN(size_bytes),
            COUNT(*)::INTEGER
        FROM files
        GROUP BY blob_hash
        ON CONFLICT (blob_hash) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_file_blobs_object_key
        ON file_blobs(object_key)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_files_blob_hash_file_blobs'
            ) THEN
                ALTER TABLE files
                ADD CONSTRAINT fk_files_blob_hash_file_blobs
                FOREIGN KEY (blob_hash)
                REFERENCES file_blobs(blob_hash)
                ON UPDATE CASCADE;
            END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE files
        DROP CONSTRAINT IF EXISTS fk_files_blob_hash_file_blobs
        """
    )
    op.execute("DROP TABLE IF EXISTS file_blobs")
