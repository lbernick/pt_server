from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from client import get_anthropic_client
from onboarding import router as onboarding_router
from templates_api import router as templates_router
from workout import router as workout_router
from workouts_api import router as workouts_api_router

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="PT Server", version="1.0.0")


@app.middleware("http")
async def log_internal_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except HTTPException as e:
        if e.status_code == 500:
            print(
                f"Unhandled exception during request: {request.method} "
                f"{request.url}. Error: {e.detail}"
            )
        raise


# Include routers
app.include_router(onboarding_router)
app.include_router(workout_router)
app.include_router(workouts_api_router)
app.include_router(templates_router)


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
        raise HTTPException(status_code=500, detail=str(e)) from e
