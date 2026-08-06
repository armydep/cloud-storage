"""Add user-to-user file shares

Revision ID: c6f7a8b9d0e1
Revises: b5e2a91c7f34
Create Date: 2026-08-06 21:00:00.000000

"""
from alembic import op


revision = "c6f7a8b9d0e1"
down_revision = "b5e2a91c7f34"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_shares (
            id UUID PRIMARY KEY,
            file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            recipient_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_file_shares_file_recipient
                UNIQUE (file_id, recipient_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_file_shares_file_id ON file_shares(file_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_file_shares_recipient_id "
        "ON file_shares(recipient_id)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS file_shares")
