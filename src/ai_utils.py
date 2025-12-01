"""Shared utilities for AI agent interactions."""

import json
from typing import List, Type, TypeVar

from anthropic import Anthropic
from fastapi import HTTPException
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def clean_json_response(response_text: str) -> str:
    """Remove markdown code blocks from AI response if present.

    Args:
        response_text: Raw text response from AI

    Returns:
        Cleaned JSON string
    """
    text = response_text.strip()

    # Remove markdown code blocks if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return text


def call_ai_agent(
    client: Anthropic,
    system_prompt: str,
    messages: List[dict],
    response_model: Type[T],
    max_tokens: int = 4096,
    model: str = "claude-sonnet-4-20250514",
    error_prefix: str = "AI agent",
) -> T:
    """Make a request to the AI agent and parse the response.

    Args:
        client: Anthropic client instance
        system_prompt: System prompt for the AI
        messages: List of message dicts with 'role' and 'content'
        response_model: Pydantic model class to parse response into
        max_tokens: Maximum tokens for response (default: 4096)
        model: Model to use (default: claude-sonnet-4-20250514)
        error_prefix: Prefix for error messages (default: "AI agent")

    Returns:
        Instance of response_model parsed from AI response

    Raises:
        HTTPException: If parsing fails or AI request fails
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )

        response_text = response.content[0].text
        cleaned_text = clean_json_response(response_text)

        data = json.loads(cleaned_text)
        return response_model(**data)

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"{error_prefix} returned invalid JSON: {str(e)}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"{error_prefix} request failed: {str(e)}"
        ) from e
