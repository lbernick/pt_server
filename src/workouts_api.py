"""REST API endpoints for workout CRUD operations."""

import datetime
from typing import List, Optional
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_utils import call_ai_agent
from auth import AuthenticatedUser, get_or_create_user
from client import get_anthropic_client
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


class WorkoutSuggestionsRequest(BaseModel):
    """Optional context for generating workout suggestions."""

    training_phase: Optional[str] = None
    goal: Optional[str] = None
    notes: Optional[str] = None


class SetSuggestion(BaseModel):
    """Suggested parameters for a single set."""

    reps: int
    weight: float


class ExerciseSuggestion(BaseModel):
    """Suggestions for one exercise."""

    name: str
    sets: List[SetSuggestion]
    notes: Optional[str] = None


class WorkoutSuggestionsResponse(BaseModel):
    """AI-generated suggestions."""

    exercises: List[ExerciseSuggestion]
    overall_notes: Optional[str] = None


# ========== Helper Functions for Workout Suggestions ==========


def get_workout_history(
    db: Session, user_id: UUID, weeks_back: int = 4
) -> List[WorkoutDB]:
    """
    Query completed workouts from the last N weeks.

    Args:
        db: Database session
        user_id: User ID to query workouts for
        weeks_back: Number of weeks to look back (default: 4)

    Returns:
        List of completed WorkoutDB objects, ordered by date descending
    """
    from datetime import timedelta

    cutoff_date = datetime.date.today() - timedelta(days=weeks_back * 7)

    return (
        db.query(WorkoutDB)
        .filter(
            WorkoutDB.user_id == user_id,
            WorkoutDB.end_time.isnot(None),  # Only completed workouts
            WorkoutDB.date >= cutoff_date,
        )
        .order_by(WorkoutDB.date.desc())
        .all()
    )


def summarize_exercise_history(workouts: List[WorkoutDB], exercise_name: str) -> dict:
    """
    Summarize performance history for a specific exercise.

    Args:
        workouts: List of completed workouts
        exercise_name: Name of the exercise to summarize

    Returns:
        Dict with recent_sessions, trend, best_performance, total_sessions
    """
    exercise_data = []

    for workout in workouts:
        if not workout.exercises:
            continue

        for exercise in workout.exercises:
            if exercise.get("name") == exercise_name:
                exercise_data.append(
                    {
                        "date": workout.date,
                        "sets": exercise.get("sets", []),
                        "target_rep_min": exercise.get("target_rep_min"),
                        "target_rep_max": exercise.get("target_rep_max"),
                    }
                )

    if not exercise_data:
        return {
            "recent_sessions": [],
            "trend": "no_data",
            "best_performance": None,
            "total_sessions": 0,
        }

    # Extract most recent 3 sessions
    recent_sessions = exercise_data[:3]

    # Find best performance (heaviest weight × reps)
    best_weight = 0.0
    best_reps = 0
    for session in exercise_data:
        for s in session["sets"]:
            if s.get("completed") and s.get("weight") and s.get("reps"):
                if s["weight"] > best_weight or (
                    s["weight"] == best_weight and s["reps"] > best_reps
                ):
                    best_weight = s["weight"]
                    best_reps = s["reps"]

    # Determine trend (simple: compare avg weight of first half vs second half)
    trend = "stable"
    if len(exercise_data) >= 4:
        half = len(exercise_data) // 2
        first_half_weights = []
        second_half_weights = []

        for session in exercise_data[:half]:
            for s in session["sets"]:
                if s.get("completed") and s.get("weight"):
                    first_half_weights.append(s["weight"])

        for session in exercise_data[half:]:
            for s in session["sets"]:
                if s.get("completed") and s.get("weight"):
                    second_half_weights.append(s["weight"])

        if first_half_weights and second_half_weights:
            avg_first = sum(first_half_weights) / len(first_half_weights)
            avg_second = sum(second_half_weights) / len(second_half_weights)

            if avg_first > avg_second * 1.05:  # 5% threshold
                trend = "increasing"
            elif avg_second > avg_first * 1.05:
                trend = "decreasing"

    return {
        "recent_sessions": recent_sessions,
        "trend": trend,
        "best_performance": {
            "weight": best_weight,
            "reps": best_reps,
        }
        if best_weight > 0
        else None,
        "total_sessions": len(exercise_data),
    }


def format_template_exercises(exercises: List[dict]) -> str:
    """Format template exercises for readability in AI prompt."""
    lines = []
    for ex in exercises:
        lines.append(
            f"- {ex['name']}: "
            f"{ex['target_sets']} sets × "
            f"{ex['target_rep_min']}-{ex['target_rep_max']} reps"
        )
    return "\n".join(lines)


def build_history_summary(workout: WorkoutDB, history: List[WorkoutDB]) -> str:
    """
    Build condensed text summary of relevant history for AI prompt.

    Args:
        workout: The workout to generate suggestions for
        history: List of completed workouts from history

    Returns:
        Formatted string summarizing performance history
    """
    if not workout.exercises:
        return "No template exercises available."

    summary_parts = []

    for template_exercise in workout.exercises:
        exercise_name = template_exercise["name"]
        exercise_summary = summarize_exercise_history(history, exercise_name)

        if exercise_summary["total_sessions"] == 0:
            summary_parts.append(f"{exercise_name}:\n  No previous history found.")
        else:
            # Format recent sessions compactly
            recent_lines = []
            for session in exercise_summary["recent_sessions"]:
                # Summarize sets
                completed_sets = [
                    s for s in session["sets"] if s.get("completed", False)
                ]
                if completed_sets:
                    weights = [
                        s.get("weight", 0) for s in completed_sets if s.get("weight")
                    ]
                    reps = [s.get("reps", 0) for s in completed_sets if s.get("reps")]

                    if weights and reps:
                        avg_weight = sum(weights) / len(weights)
                        avg_reps = sum(reps) / len(reps)
                        recent_lines.append(
                            f"{session['date']}: "
                            f"{len(completed_sets)}×{int(avg_reps)} "
                            f"@ {avg_weight:.1f} lbs"
                        )

            recent_text = (
                ", ".join(recent_lines) if recent_lines else "No completed sets"
            )

            best_text = "None"
            if exercise_summary["best_performance"]:
                best = exercise_summary["best_performance"]
                best_text = f"{best['weight']:.1f} lbs × {best['reps']} reps"

            summary_parts.append(
                f"{exercise_name}:\n"
                f"  Recent: {recent_text}\n"
                f"  Trend: {exercise_summary['trend']}\n"
                f"  Best: {best_text}"
            )

    return "\n\n".join(summary_parts)


def get_suggestion_system_prompt() -> str:
    """System prompt instructing Claude on how to provide suggestions."""
    import json

    schema = WorkoutSuggestionsResponse.model_json_schema()

    return f"""You are an expert strength and conditioning coach providing \
personalized workout suggestions.

Your task is to suggest specific sets, reps, and weights for a scheduled \
workout based on:
1. The workout's template prescription (target sets and rep ranges)
2. The athlete's performance history over the last 4 weeks
3. Progressive overload principles
4. Optional training context (phase, goals)

CRITICAL GUIDELINES:
- Suggest weights that are challenging but achievable within the target \
rep range
- Apply progressive overload when trend shows readiness (typically \
+2.5-5 lbs or +1 rep)
- For exercises with no history, suggest conservative starting weights \
based on the exercise type
- Consider fatigue accumulation (later sets may need lower reps or weight)
- Respect deload phases if mentioned in training context
- Use the exercise 'notes' field to explain your reasoning and strategy

RESPONSE FORMAT:
Return ONLY valid JSON matching this exact schema:

{json.dumps(schema, indent=2)}

No markdown, no code blocks, no explanations outside the JSON structure."""


def build_suggestion_user_prompt(
    workout: WorkoutDB,
    history_summary: str,
    request: WorkoutSuggestionsRequest,
) -> str:
    """
    Build user prompt with all context for generating suggestions.

    Args:
        workout: The workout to generate suggestions for
        history_summary: Formatted history summary
        request: User's optional context

    Returns:
        Formatted user prompt for AI
    """
    template_info = format_template_exercises(workout.exercises)

    prompt_parts = [
        "Generate workout suggestions for the following session:",
        "",
        "TEMPLATE PRESCRIPTION:",
        template_info,
        "",
        "PERFORMANCE HISTORY (Last 4 weeks):",
        history_summary,
    ]

    if request.training_phase:
        prompt_parts.extend(["", f"TRAINING PHASE: {request.training_phase}"])

    if request.goal:
        prompt_parts.extend(["", f"TRAINING GOAL: {request.goal}"])

    if request.notes:
        prompt_parts.extend(["", f"ADDITIONAL NOTES: {request.notes}"])

    return "\n".join(prompt_parts)


# ========== API Endpoints ==========


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

    # Prevent modifications to finished workouts
    if db_workout.end_time is not None:
        raise HTTPException(status_code=400, detail="Cannot modify a finished workout")

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

    # Prevent modifications to finished workouts
    if workout.end_time is not None:
        raise HTTPException(status_code=400, detail="Cannot modify a finished workout")

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

    Can only start workouts that haven't been started yet (start_time is None)
    and are scheduled for today.
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

    # Validate: can only start today's workouts
    today = datetime.date.today()
    if workout.date != today:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Can only start workouts scheduled for today. "
                f"This workout is scheduled for {workout.date}"
            ),
        )

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


@router.post("/{workout_id}/suggest", response_model=WorkoutSuggestionsResponse)
def suggest_workout_parameters(
    workout_id: UUID,
    request: WorkoutSuggestionsRequest = WorkoutSuggestionsRequest(),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
    client: Anthropic = Depends(get_anthropic_client),
) -> WorkoutSuggestionsResponse:
    """Generate AI-powered suggestions for workout reps and weights.

    Analyzes the workout's template prescription and the last 4 weeks of
    completed workout history to provide personalized rep and weight suggestions.

    This is a read-only endpoint - suggestions are returned but NOT applied
    to the workout. Use PATCH /workouts/{id}/exercises to apply suggestions.

    Args:
        workout_id: ID of the workout to generate suggestions for
        request: Optional training context (phase, goal, notes)
        db: Database session
        user: Authenticated user
        client: Anthropic AI client

    Returns:
        WorkoutSuggestionsResponse with exercise-level suggestions

    Raises:
        404: Workout not found
        400: Workout already completed or has no template
    """
    # 1. Validate workout exists and belongs to user
    workout = (
        db.query(WorkoutDB)
        .filter(WorkoutDB.id == workout_id, WorkoutDB.user_id == user.user_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # 2. Validate workout is not completed
    if workout.end_time is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate suggestions for completed workouts",
        )

    # 3. Validate workout has a template
    if not workout.template_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate suggestions for workouts without a template",
        )

    # 4. Snapshot template exercises if needed
    if workout.exercises is None:
        from workout import snapshot_template_exercises

        workout.exercises = snapshot_template_exercises(db, workout.template_id)
        db.commit()
        db.refresh(workout)

    # 5. Query workout history (last 4 weeks)
    history = get_workout_history(db, user.user_id, weeks_back=4)

    # 6. Build history summary for AI prompt
    history_summary = build_history_summary(workout, history)

    # 7. Build AI prompts
    system_prompt = get_suggestion_system_prompt()
    user_prompt = build_suggestion_user_prompt(workout, history_summary, request)

    # 8. Call AI agent to generate suggestions
    suggestions = call_ai_agent(
        client=client,
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        response_model=WorkoutSuggestionsResponse,
        max_tokens=4096,
        error_prefix="Workout suggestions",
    )

    return suggestions
