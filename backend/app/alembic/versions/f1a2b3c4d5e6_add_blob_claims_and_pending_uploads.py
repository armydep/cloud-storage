"""Add blob claims and pending uploads

Revision ID: f1a2b3c4d5e6
Revises: e8c9d0a1b2c3
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op


revision = "f1a2b3c4d5e6"
down_revision = "e8c9d0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_blob_claims (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            blob_hash TEXT NOT NULL REFERENCES file_blobs(blob_hash) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_file_blob_claims_owner_blob UNIQUE (owner_id, blob_hash)
        )
        """
    )
    op.execute(
        """
        INSERT INTO file_blob_claims (id, owner_id, blob_hash, created_at)
        SELECT uuid_generate_v4(), owner_id, blob_hash, NOW()
        FROM files
        GROUP BY owner_id, blob_hash
        ON CONFLICT (owner_id, blob_hash) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_file_blob_claims_owner_id
        ON file_blob_claims(owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_file_blob_claims_blob_hash
        ON file_blob_claims(blob_hash)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_uploads (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            blob_hash TEXT NOT NULL,
            object_key TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            mime_type TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_pending_uploads_object_key UNIQUE (object_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pending_uploads_owner_blob
        ON pending_uploads(owner_id, blob_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pending_uploads_expires_at
        ON pending_uploads(expires_at)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS pending_uploads")
    op.execute("DROP TABLE IF EXISTS file_blob_claims")
