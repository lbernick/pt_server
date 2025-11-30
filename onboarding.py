import json
from typing import List

from anthropic import Anthropic
from fastapi import APIRouter, Depends

from models import OnboardingRequest, OnboardingResponse, OnboardingState


# Placeholder dependency that will be overridden by main.py
def get_client() -> Anthropic:
    """Placeholder - overridden by main.py's get_anthropic_client"""
    raise NotImplementedError("Client dependency not configured")


class OnboardingAgent:
    def __init__(self, client: Anthropic):
        self.client = client

    def get_system_prompt(self) -> str:
        return """You are an expert fitness coach conducting an intake interview with a new client.

Your goal is to gather enough information to create a personalized 12-week workout plan. You need to understand:

1. FITNESS GOALS
   - What they want to achieve (strength, muscle gain, weight loss, athletic performance, general fitness)
   - Timeline and specific targets if any
   - Priority goals if multiple

2. CURRENT FITNESS LEVEL & ROUTINE
   - Experience with training (beginner, intermediate, advanced)
   - Current routine (if any) - exercises, frequency, duration
   - Strength levels or fitness benchmarks if known
   - What's worked or not worked in the past

3. LOGISTICAL CONSTRAINTS
   - Days per week available
   - Time per session
   - Equipment access (gym, home gym, bodyweight only)
   - Schedule constraints (morning/evening, etc.)
   - Any injuries or limitations

CONVERSATION STYLE:
- Be warm, encouraging, and conversational
- Ask 1-2 questions at a time (don't overwhelm)
- Ask follow-up questions based on their answers
- If they're vague, probe for specifics
- Use their language and tone
- When you have enough information, summarize what you learned and confirm

You must respond with JSON in this exact format:
{
  "message": "Your response to the user",
  "is_complete": false,  // Set to true only when you have ALL necessary information
  "state": {
    "fitness_goals": ["list", "of", "goals"],  // null if not yet known
    "experience_level": "beginner|intermediate|advanced",  // null if not yet known
    "current_routine": "description of current routine",  // null if not yet known
    "days_per_week": 4,  // null if not yet known
    "session_duration_minutes": 60,  // null if not yet known
    "equipment_available": ["list", "of", "equipment"],  // null if not yet known
    "injuries_limitations": ["list"],  // null or empty list
    "preferences": {}  // any other relevant info
  }
}

CRITICAL:
- Only set is_complete to true when you have sufficient information for ALL categories
- Always include the full state object with all fields (use null for unknowns)
- Return ONLY valid JSON, no markdown, no code blocks"""

    def process_message(
        self, conversation_history: List[dict], latest_message: str
    ) -> OnboardingResponse:
        """Process user's message and determine next question"""

        # Add latest message to history
        messages = conversation_history + [{"role": "user", "content": latest_message}]

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=self.get_system_prompt(),
            messages=messages,
        )

        response_text = response.content[0].text.strip()

        # Clean response
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        try:
            data = json.loads(response_text)
            return OnboardingResponse(**data)
        except Exception as e:
            # Fallback if parsing fails
            return OnboardingResponse(
                message="I'm having trouble processing that. Could you tell me a bit about your fitness goals?",
                is_complete=False,
                state=OnboardingState(),
            )

    def start_conversation(self) -> OnboardingResponse:
        """Generate the opening message"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=self.get_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": "Start the onboarding conversation. Greet the user and ask your first question.",
                }
            ],
        )

        response_text = response.content[0].text.strip()

        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        data = json.loads(response_text)
        return OnboardingResponse(**data)


# Create router for onboarding endpoints
router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/start")
async def start_onboarding(client: Anthropic = Depends(get_client)):
    """Start the onboarding conversation"""
    agent = OnboardingAgent(client)
    response = agent.start_conversation()

    return {
        "conversation_id": "conv_123",  # Generate real ID in production
        "response": response,
    }


@router.post("/message")
async def onboarding_message(
    request: OnboardingRequest, client: Anthropic = Depends(get_client)
):
    """Continue the onboarding conversation"""
    agent = OnboardingAgent(client)

    response = agent.process_message(
        conversation_history=request.conversation_history,
        latest_message=request.latest_message,
    )

    # If complete, optionally trigger plan generation
    if response.is_complete:
        # Could start plan generation in background here
        pass

    return response


@router.post("/complete")
async def complete_onboarding(state: OnboardingState):
    """Called when onboarding is complete to generate the plan"""
    pass
