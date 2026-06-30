"""remove_auto_default_projects

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-07-01 00:00:00.000000

Remove migration-created default projects ("Мой бизнес").
Agents and websites are unlinked (project_id → NULL); entities stay standalone.
"""
from alembic import op

revision = "c4d5e6f7g8h9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade():
    # Unlink agents from auto-created default projects
    op.execute("""
        UPDATE agents a
        SET project_id = NULL
        FROM projects p
        WHERE a.project_id = p.id
          AND p.is_default = true
    """)

    # Unlink websites from auto-created default projects
    op.execute("""
        UPDATE websites w
        SET project_id = NULL
        FROM projects p
        WHERE w.project_id = p.id
          AND p.is_default = true
    """)

    # project_documents are removed via ON DELETE CASCADE
    op.execute("""
        DELETE FROM projects
        WHERE is_default = true
    """)


def downgrade():
    # Data loss is intentional; auto-default projects are not restored.
    pass
