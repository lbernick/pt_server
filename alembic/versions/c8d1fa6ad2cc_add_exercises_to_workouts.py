"""add_exercises_to_workouts

Revision ID: c8d1fa6ad2cc
Revises: 3736e8f8d616
Create Date: 2025-12-10 08:33:30.963669

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d1fa6ad2cc"
down_revision: Union[str, None] = "3736e8f8d616"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add exercises column to workouts table
    op.add_column("workouts", sa.Column("exercises", JSONB, nullable=True))

    # Create GIN index for JSONB querying
    op.create_index(
        op.f("ix_workouts_exercises"),
        "workouts",
        ["exercises"],
        unique=False,
        postgresql_using="gin",
    )

    # Update FK constraint to SET NULL on template deletion
    op.drop_constraint("fk_workouts_template_id", "workouts", type_="foreignkey")
    op.create_foreign_key(
        "fk_workouts_template_id",
        "workouts",
        "templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Restore original FK constraint (no ondelete behavior)
    op.drop_constraint("fk_workouts_template_id", "workouts", type_="foreignkey")
    op.create_foreign_key(
        "fk_workouts_template_id", "workouts", "templates", ["template_id"], ["id"]
    )

    # Drop index and column
    op.drop_index(op.f("ix_workouts_exercises"), table_name="workouts")
    op.drop_column("workouts", "exercises")
