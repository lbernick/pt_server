"""SQLAlchemy database models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database import Base


class WorkoutDB(Base):
    """Database model for workouts."""

    __tablename__ = "workouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    def __repr__(self):
        return f"<WorkoutDB(id={self.id}, date={self.date})>"


class TemplateDB(Base):
    """Database model for workout templates.

    Templates are reusable workout definitions that specify exercises.
    They are referenced by ScheduleItems to build training plans.
    """

    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    exercises = Column(JSONB, nullable=False)  # Array of exercise names as strings
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    def __repr__(self):
        return f"<TemplateDB(id={self.id}, name={self.name})>"


class TrainingPlanDB(Base):
    """Database model for training plans.

    A training plan describes a weekly schedule of workouts.
    The actual schedule is defined by related ScheduleItems.
    """

    __tablename__ = "training_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    # Relationship to schedule items (ordered by day_index)
    schedule_items = relationship(
        "ScheduleItemDB",
        order_by="ScheduleItemDB.day_index",
        back_populates="training_plan",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TrainingPlanDB(id={self.id}, description={self.description})>"


class ScheduleItemDB(Base):
    """Database model for schedule items.

    Represents a single day in a training plan's schedule.
    Links a specific day (0=Monday, 6=Sunday) to a template (or NULL for rest).
    """

    __tablename__ = "schedule_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    training_plan_id = Column(
        UUID(as_uuid=True), ForeignKey("training_plans.id"), nullable=False
    )
    template_id = Column(
        UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True
    )  # NULL = rest day
    day_index = Column(Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))

    # Relationships
    training_plan = relationship("TrainingPlanDB", back_populates="schedule_items")
    template = relationship("TemplateDB")

    # Constraints
    __table_args__ = (
        UniqueConstraint("training_plan_id", "day_index", name="uq_plan_day"),
    )

    def __repr__(self):
        return f"<ScheduleItemDB(id={self.id}, plan_id={self.training_plan_id}, day={self.day_index})>"
