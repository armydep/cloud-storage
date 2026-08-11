"""Drop legacy item table

Revision ID: 3e4f5a6b7c8d
Revises: 2d3e4f5a6b7c
Create Date: 2026-08-11 00:00:00.000000

"""

from alembic import op

revision = "3e4f5a6b7c8d"
down_revision = "2d3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS item")


def downgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS item (
            id uuid PRIMARY KEY,
            title varchar(255) NOT NULL,
            description varchar(255) NULL,
            owner_id uuid NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            created_at timestamptz NULL
        )
        """
    )
