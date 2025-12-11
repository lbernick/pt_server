"""REST API endpoints for workout CRUD operations."""

import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import AuthenticatedUser, get_or_create_user
from database import get_db
from models import WorkoutDB
from typedefs import TrackedExercise

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


class WorkoutSummaryResponse(BaseModel):
    """Response model for workout list/summary (without exercises)."""

    id: UUID
    template_id: Optional[UUID]
    date: datetime.date
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]

    class Config:
        from_attributes = True


class WorkoutResponse(BaseModel):
    """Response model for a single workout (with exercises)."""

    id: UUID
    template_id: Optional[UUID]
    date: datetime.date
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    exercises: Optional[List["TrackedExercise"]]

    class Config:
        from_attributes = True


class WorkoutUpdateExercisesRequest(BaseModel):
    """Request to update workout exercises."""

    exercises: List["TrackedExercise"]


@router.post("", response_model=WorkoutResponse, status_code=201)
def create_workout(
    workout: WorkoutCreateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Create a new workout for the authenticated user."""
    db_workout = WorkoutDB(
        user_id=user.user_id,
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
    skip: int = 0,
    limit: int = 100,
    date: datetime.date | None = None,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> List[WorkoutResponse]:
    """List all workouts for the authenticated user with pagination.

    When listing without a date filter, returns workout summaries without
    exercise data to keep responses compact. When filtering by a specific date,
    returns full workout details including exercises.

    Args:
        skip: Number of workouts to skip (default: 0)
        limit: Maximum number of workouts to return (default: 100)
        date: Optional date filter (YYYY-MM-DD format) to get workouts for a
            specific day. When provided, includes exercise data in response.
        db: Database session
        user: Authenticated user

    Returns:
        List of WorkoutResponse objects. Exercises are included only when
        date filter is applied.
    """
    query = db.query(WorkoutDB).filter(WorkoutDB.user_id == user.user_id)

    # Apply date filter if provided
    if date is not None:
        query = query.filter(WorkoutDB.date == date)

    workouts = query.offset(skip).limit(limit).all()

    # When filtering by date, snapshot exercises for workouts that need it
    if date is not None:
        for workout in workouts:
            if workout.template_id and workout.exercises is None:
                from workout import snapshot_template_exercises

                workout.exercises = snapshot_template_exercises(db, workout.template_id)
        db.commit()

    return [WorkoutResponse.model_validate(w) for w in workouts]


@router.get("/{workout_id}", response_model=WorkoutResponse)
def get_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Get a specific workout by ID (must belong to authenticated user).

    If the workout has a template but no exercises yet (future workout),
    this will snapshot the template exercises for editing.
    """
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Snapshot template exercises if not yet snapshotted
    if workout.template_id and workout.exercises is None:
        from workout import snapshot_template_exercises

        workout.exercises = snapshot_template_exercises(db, workout.template_id)
        db.commit()
        db.refresh(workout)

    return WorkoutResponse.model_validate(workout)


@router.patch("/{workout_id}", response_model=WorkoutResponse)
def update_workout(
    workout_id: UUID,
    workout: WorkoutUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Partially update an existing workout (must belong to authenticated user).

    If start_time is being set, this will snapshot template exercises to enable
    workout tracking.
    """
    db_workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Use model_dump with exclude_unset=True to only get fields that were explicitly set
    update_data = workout.model_dump(exclude_unset=True)

    # Snapshot on start if needed
    if "start_time" in update_data and update_data["start_time"] is not None:
        if db_workout.exercises is None and db_workout.template_id:
            from workout import snapshot_template_exercises

            db_workout.exercises = snapshot_template_exercises(
                db, db_workout.template_id
            )

    for field, value in update_data.items():
        setattr(db_workout, field, value)

    db.commit()
    db.refresh(db_workout)
    return WorkoutResponse.model_validate(db_workout)


@router.patch("/{workout_id}/exercises", response_model=WorkoutResponse)
def update_workout_exercises(
    workout_id: UUID,
    request: WorkoutUpdateExercisesRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Update exercises for a specific workout.

    This endpoint allows users to customize exercises for an individual
    workout without affecting the template. If the workout doesn't have
    exercises yet, it will snapshot the template first, then apply updates.
    """
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Snapshot first if needed
    if workout.exercises is None and workout.template_id:
        from workout import snapshot_template_exercises

        workout.exercises = snapshot_template_exercises(db, workout.template_id)

    # Update exercises with user's data
    workout.exercises = [ex.model_dump() for ex in request.exercises]

    db.commit()
    db.refresh(workout)
    return WorkoutResponse.model_validate(workout)


@router.post("/{workout_id}/start", response_model=WorkoutResponse)
def start_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Start a workout by setting start_time to now.

    Can only start workouts that haven't been started yet (start_time is None).
    If the workout has a template but no exercises, this will snapshot them.
    """
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Validate: can only start if not already started
    if workout.start_time is not None:
        raise HTTPException(status_code=400, detail="Workout has already been started")

    # Set start_time to now
    workout.start_time = datetime.datetime.now(datetime.UTC)

    # Snapshot exercises if workout has template but no exercises yet
    if workout.template_id and workout.exercises is None:
        from workout import snapshot_template_exercises

        workout.exercises = snapshot_template_exercises(db, workout.template_id)

    db.commit()
    db.refresh(workout)
    return WorkoutResponse.model_validate(workout)


@router.post("/{workout_id}/cancel", response_model=WorkoutResponse)
def cancel_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Cancel a workout in progress by clearing start_time.

    Can only cancel workouts that are in progress (start_time is set, end_time is None).
    """
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Validate: workout must be in progress
    if workout.start_time is None:
        raise HTTPException(status_code=400, detail="Workout has not been started")
    if workout.end_time is not None:
        raise HTTPException(status_code=400, detail="Workout has already been finished")

    # Clear start_time
    workout.start_time = None

    db.commit()
    db.refresh(workout)
    return WorkoutResponse.model_validate(workout)


@router.post("/{workout_id}/finish", response_model=WorkoutResponse)
def finish_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> WorkoutResponse:
    """Finish a workout by setting end_time to now.

    Can only finish workouts that are in progress (start_time is set, end_time is None).
    """
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Validate: workout must be in progress
    if workout.start_time is None:
        raise HTTPException(status_code=400, detail="Workout has not been started")
    if workout.end_time is not None:
        raise HTTPException(status_code=400, detail="Workout has already been finished")

    # Set end_time to now
    workout.end_time = datetime.datetime.now(datetime.UTC)

    db.commit()
    db.refresh(workout)
    return WorkoutResponse.model_validate(workout)


@router.delete("/{workout_id}", status_code=204)
def delete_workout(
    workout_id: UUID,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
) -> None:
    """Delete a workout (must belong to authenticated user)."""
    db_workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    db.delete(db_workout)
    db.commit()
