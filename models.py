from typing import List, Literal

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
    reps: int
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


class OnboardingMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class OnboardingState(BaseModel):
    fitness_goals: List[str] | None = None
    experience_level: str | None = None
    current_routine: str | None = None
    days_per_week: int | None = None
    session_duration_minutes: int | None = None
    equipment_available: List[str] | None = None
    injuries_limitations: List[str] | None = None
    preferences: dict | None = None  # e.g., {"likes_cardio": false}


class OnboardingResponse(BaseModel):
    message: str  # AI's next question or statement
    is_complete: bool  # True when ready to generate plan
    state: OnboardingState  # Current understanding
    confidence: float | None = None  # How confident AI is (optional)


class OnboardingRequest(BaseModel):
    conversation_history: List[OnboardingMessage]
    latest_message: str
