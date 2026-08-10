"""Add notifications feed

Revision ID: 2d3e4f5a6b7c
Revises: 1c2d3e4f5a6b
Create Date: 2026-08-10 00:00:00.000000

"""

from alembic import op

revision = "2d3e4f5a6b7c"
down_revision = "1c2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id uuid PRIMARY KEY,
            outbox_id uuid NOT NULL REFERENCES notification_outbox (id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
            event_type text NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            read_at timestamptz NULL,
            CONSTRAINT uq_notifications_outbox_id UNIQUE (outbox_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notifications_user_created_at
        ON notifications (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notifications_user_unread
        ON notifications (user_id)
        WHERE read_at IS NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_unread")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_created_at")
    op.execute("DROP TABLE IF EXISTS notifications")
