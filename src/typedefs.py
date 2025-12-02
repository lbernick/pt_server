from datetime import datetime
from typing import List, Literal
from uuid import UUID

from pydantic import BaseModel


class Equipment(BaseModel):
    name: str


class Exercise(BaseModel):
    # TODO: Exercises should be identifiable by ID rather than name
    name: str
    # TODO: How to represent exercises that can be done with different types of equipment?
    # e.g. a goblet squat can be done with a dumbbell or kettlebell
    equipment: Equipment


class Set(BaseModel):
    reps: int  # TODO: AMRAP
    weight: float | None = None
    # TODO: Weight units?
    duration_seconds: int | None = None
    rest_seconds: int | None = None


class WorkoutExercise(BaseModel):
    exercise: Exercise
    sets: List[Set]


class Workout(BaseModel):
    # TODO: Notes, focus, estimated duration
    exercises: List[WorkoutExercise]


class Template(BaseModel):
    name: str
    description: str | None = None
    exercises: List[str]


# TODO: Ideally a training plan would be more flexible than this
# (e.g. biweekly repetition, training blocks, deload weeks, multiple workouts per day, etc)
class TrainingPlan(BaseModel):
    description: str
    templates: List[Template]
    microcycle: List[
        int
    ]  # The index of the template to use on each day of the microcycle, or None for no workout


class OnboardingMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class OnboardingState(BaseModel):
    fitness_goals: List[str] | None = None
    experience_level: str | None = None
    current_routine: str | None = None
    days_per_week: int | None = None
    equipment_available: List[str] | None = None
    injuries_limitations: List[str] | None = None
    preferences: str | None = None


class OnboardingResponse(BaseModel):
    message: str  # AI's next question or statement
    is_complete: bool  # True when ready to generate plan
    state: OnboardingState  # Current understanding


class OnboardingRequest(BaseModel):
    conversation_history: List[OnboardingMessage] = []
    latest_message: str = ""


# Response models with DB IDs (for API responses)
class TemplateResponse(BaseModel):
    """Template response model with database ID."""

    id: UUID
    name: str
    description: str | None = None
    exercises: List[str]

    class Config:
        from_attributes = True


class TrainingPlanResponse(BaseModel):
    """Training plan response model with database ID and microcycle format."""

    id: UUID
    description: str
    templates: List[TemplateResponse]
    microcycle: List[int]  # Array of template indices (-1 for rest days)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
