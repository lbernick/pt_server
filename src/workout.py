import json

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from typedefs import Workout

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

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=get_workout_schema_prompt(),
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        workout_data = json.loads(response_text)
        workout = Workout(**workout_data)

        return workout

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to parse workout JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
