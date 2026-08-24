"""add user quota columns

Revision ID: d67bd8ce7bc2
Revises: f44fbc45deb1
Create Date: 2026-08-24 15:00:00.000000

"""

from alembic import op

revision = "d67bd8ce7bc2"
down_revision = "f44fbc45deb1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE "user"
        ADD COLUMN IF NOT EXISTS quota_bytes bigint NULL
        """
    )
    op.execute(
        """
        ALTER TABLE "user"
        ADD COLUMN IF NOT EXISTS quota_notified_threshold integer NULL
        """
    )


def downgrade():
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS quota_notified_threshold')
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS quota_bytes')
