import os

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="PT Server", version="1.0.0")
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


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
async def chat(request: ChatRequest):
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
