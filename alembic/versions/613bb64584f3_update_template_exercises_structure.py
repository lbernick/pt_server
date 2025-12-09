"""update template exercises structure

Revision ID: 613bb64584f3
Revises: 9376194187a4
Create Date: 2025-12-09 18:15:44.621750

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "613bb64584f3"
down_revision: Union[str, None] = "9376194187a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update column comment to reflect new structure (JSONB schema is flexible)
    op.execute("""
        COMMENT ON COLUMN templates.exercises IS
        'Array of TemplateExercise objects with name, sets, rep_min, rep_max'
    """)


def downgrade() -> None:
    # Restore original comment
    op.execute("""
        COMMENT ON COLUMN templates.exercises IS
        'Array of exercise names as strings'
    """)
