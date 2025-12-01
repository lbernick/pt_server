"""SQLAlchemy database models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID

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
