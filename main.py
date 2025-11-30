import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from models import Workout

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="PT Server", version="1.0.0")


def get_anthropic_client() -> Anthropic:
    """Dependency function that returns the Anthropic client."""
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@app.get("/")
async def root():
    return {"message": "Welcome to PT Server"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]  # Client sends full conversation
    max_tokens: int = 1024


@app.post("/api/v1/chat")
async def chat(request: ChatRequest, client: Anthropic = Depends(get_anthropic_client)):
    try:
        # Convert to format Anthropic expects
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=request.max_tokens,
            messages=messages,
        )

        return {"role": "assistant", "content": response.content[0].text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/api/v1/generate-workout", response_model=Workout)
async def generate_workout(
    request: WorkoutRequest, client: Anthropic = Depends(get_anthropic_client)
):
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
