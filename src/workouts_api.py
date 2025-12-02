"""REST API endpoints for workout CRUD operations."""

import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import WorkoutDB

router = APIRouter(prefix="/api/v1/workouts", tags=["workouts"])


class WorkoutCreateRequest(BaseModel):
    """Request model for creating a workout."""

    date: datetime.date
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None


class WorkoutUpdateRequest(BaseModel):
    """Request model for updating a workout (PATCH - partial update).

    All fields are optional - only provided fields will be updated.
    """

    date: datetime.date | None = None
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None


class WorkoutResponse(BaseModel):
    """Response model for a workout."""

    id: UUID
    date: datetime.date
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


@router.post("", response_model=WorkoutResponse, status_code=201)
def create_workout(
    workout: WorkoutCreateRequest, db: Session = Depends(get_db)
) -> WorkoutResponse:
    """Create a new workout."""
    db_workout = WorkoutDB(
        date=workout.date,
        start_time=workout.start_time,
        end_time=workout.end_time,
    )
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return WorkoutResponse.model_validate(db_workout)


@router.get("", response_model=List[WorkoutResponse])
def list_workouts(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> List[WorkoutResponse]:
    """List all workouts with pagination."""
    workouts = db.query(WorkoutDB).offset(skip).limit(limit).all()
    return [WorkoutResponse.model_validate(w) for w in workouts]


@router.get("/{workout_id}", response_model=WorkoutResponse)
def get_workout(workout_id: UUID, db: Session = Depends(get_db)) -> WorkoutResponse:
    """Get a specific workout by ID."""
    workout = db.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutResponse.model_validate(workout)


@router.patch("/{workout_id}", response_model=WorkoutResponse)
def update_workout(
    workout_id: UUID,
    workout: WorkoutUpdateRequest,
    db: Session = Depends(get_db),
) -> WorkoutResponse:
    """Partially update an existing workout."""
    db_workout = db.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Use model_dump with exclude_unset=True to only get fields that were explicitly set
    update_data = workout.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_workout, field, value)

    db.commit()
    db.refresh(db_workout)
    return WorkoutResponse.model_validate(db_workout)


@router.delete("/{workout_id}", status_code=204)
def delete_workout(workout_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a workout."""
    db_workout = db.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    db.delete(db_workout)
    db.commit()
