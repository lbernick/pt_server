from typing import List

from pydantic import BaseModel


class Equipment(BaseModel):
    name: str


class Exercise(BaseModel):
    name: str
    # TODO: How to represent exercises that can be done with different types of equipment?
    # e.g. a goblet squat can be done with a dumbbell or kettlebell
    equipment: Equipment


class Set(BaseModel):
    reps: int
    weight: float | None = None
    # TODO: Weight units?
    rest_seconds: int | None = None


class WorkoutExercise(BaseModel):
    exercise: Exercise
    sets: List[Set]


class Workout(BaseModel):
    # TODO: Notes, focus, estimated duration
    exercises: List[WorkoutExercise]
