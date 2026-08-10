"""Add notification outbox

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
Create Date: 2026-08-10 00:00:00.000000

"""

from alembic import op

revision = "1c2d3e4f5a6b"
down_revision = "0b1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_outbox (
            id uuid PRIMARY KEY,
            event_type text NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            published_at timestamptz NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notification_outbox_unpublished_created_at
        ON notification_outbox (created_at)
        WHERE published_at IS NULL
        """
    )


def downgrade():
    op.execute(
        "DROP INDEX IF EXISTS ix_notification_outbox_unpublished_created_at"
    )
    op.execute("DROP TABLE IF EXISTS notification_outbox")
