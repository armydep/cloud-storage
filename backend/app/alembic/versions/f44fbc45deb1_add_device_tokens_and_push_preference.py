"""add device tokens and push preference

Revision ID: f44fbc45deb1
Revises: 3e4f5a6b7c8d
Create Date: 2026-08-23 12:28:19.170058

"""

from alembic import op

revision = "f44fbc45deb1"
down_revision = "3e4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE "user"
        ADD COLUMN IF NOT EXISTS push_enabled boolean NOT NULL DEFAULT false
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS device_tokens (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
            token text NOT NULL,
            platform text NOT NULL,
            created_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            CONSTRAINT uq_device_tokens_token UNIQUE (token)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_device_tokens_user_id
        ON device_tokens (user_id)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS device_tokens")
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS push_enabled')
