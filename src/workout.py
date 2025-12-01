import json

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_utils import call_ai_agent
from typedefs import Workout, OnboardingState, TrainingPlan

router = APIRouter(prefix="/api/v1", tags=["workout"])


# Placeholder dependency that will be overridden by main.py
def get_client() -> Anthropic:
    """Placeholder - overridden by main.py's get_anthropic_client"""
    raise NotImplementedError("Client dependency not configured")


class WorkoutRequest(BaseModel):
    prompt: str
    difficulty: str | None = None
    duration_minutes: int | None = None


def get_workout_schema_prompt() -> str:
    """Generate schema description from Pydantic model"""
    schema = Workout.model_json_schema()
    return f"""You are a fitness expert. Generate workout plans in valid JSON format.

The JSON must match this exact schema:

{json.dumps(schema, indent=2)}

CRITICAL: Return ONLY valid JSON matching this schema. No markdown, no explanation, no code blocks."""


@router.post("/generate-workout", response_model=Workout)
async def generate_workout(
    request: WorkoutRequest, client: Anthropic = Depends(get_client)
):
    """Generate a workout based on user prompt and optional parameters."""
    user_prompt = f"Generate a workout based on: {request.prompt}"
    if request.difficulty:
        user_prompt += f"\nDifficulty: {request.difficulty}"
    if request.duration_minutes:
        user_prompt += f"\nTarget duration: {request.duration_minutes} minutes"

    return call_ai_agent(
        client=client,
        system_prompt=get_workout_schema_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
        response_model=Workout,
        max_tokens=4096,
        error_prefix="Workout generation",
    )


def get_training_plan_schema_prompt() -> str:
    """Generate schema description for TrainingPlan model"""
    schema = TrainingPlan.model_json_schema()
    return f"""You are a fitness expert creating personalized weekly training plans.

Generate a training plan in valid JSON format matching this exact schema:

{json.dumps(schema, indent=2)}

A Template contains:
- name: descriptive name for the workout (e.g., "Upper Body Strength", "Lower Body Power")
- description: brief overview of the workout's focus
- exercises: list of exercises that will be performed (e.g., "Barbell Squat", "Bench Press")

A Training plan contains:
- description: e.g. "3-day push-pull-legs strength training plan", "13-week marathon training plan"
- templates: a list of Template objects
- microcycle: a list containing the indexes of the template used on each day, or -1 for no workout.
  The microcycle will be repeated once complete and its length should be a multiple of 7,
  so that each template is repeated on the same day of the week. Assume the week starts on Monday.

Create a comprehensive weekly plan based on the user's:
- Fitness goals
- Experience level
- Available training days per week
- Available equipment
- Any injuries or limitations
- Preferences

CRITICAL: Return ONLY valid JSON matching this schema. No markdown, no explanation, no code blocks.
Assign workouts to specific days based on the days_per_week. Leave unassigned days as null."""


@router.post("/generate-training-plan", response_model=TrainingPlan)
async def generate_training_plan(
    state: OnboardingState, client: Anthropic = Depends(get_client)
):
    """Generate a weekly training plan based on onboarding information."""

    # Build the user prompt from onboarding state
    prompt_parts = [
        "Generate a weekly training plan based on the following information:"
    ]

    if state.fitness_goals:
        prompt_parts.append(f"Fitness Goals: {', '.join(state.fitness_goals)}")

    if state.experience_level:
        prompt_parts.append(f"Experience Level: {state.experience_level}")

    if state.current_routine:
        prompt_parts.append(f"Current Routine: {state.current_routine}")

    if state.days_per_week:
        prompt_parts.append(f"Training Days Per Week: {state.days_per_week}")

    if state.equipment_available:
        prompt_parts.append(
            f"Available Equipment: {', '.join(state.equipment_available)}"
        )

    if state.injuries_limitations:
        prompt_parts.append(
            f"Injuries/Limitations: {', '.join(state.injuries_limitations)}"
        )

    if state.preferences:
        prompt_parts.append(f"Preferences: {state.preferences}")

    user_prompt = "\n".join(prompt_parts)

    return call_ai_agent(
        client=client,
        system_prompt=get_training_plan_schema_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
        response_model=TrainingPlan,
        max_tokens=4096,
        error_prefix="Training plan generation",
    )
