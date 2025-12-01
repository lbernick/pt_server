from typing import List

from anthropic import Anthropic
from fastapi import APIRouter, Depends

from ai_utils import call_ai_agent
from typedefs import OnboardingRequest, OnboardingResponse, OnboardingState


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
   - Number of days per week available
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
    "fitness_goals": ["list", "of", "goals", "in", "priority", "order"],  // null if not yet known
    "experience_level": "description of current fitness and experience level",  // null if not yet known
    "current_routine": "description of current routine",  // null if not yet known
    "days_per_week": 4,  // null if not yet known
    "equipment_available": ["list", "of", "equipment"],  // null if not yet known
    "injuries_limitations": ["list"],  // null or empty list
    "preferences": "description of preferences"
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

        try:
            return call_ai_agent(
                client=self.client,
                system_prompt=self.get_system_prompt(),
                messages=messages,
                response_model=OnboardingResponse,
                max_tokens=2048,
                error_prefix="Onboarding",
            )
        except Exception:
            # Fallback if parsing fails
            return OnboardingResponse(
                message="I'm having trouble processing that. Could you tell me a bit about your fitness goals?",
                is_complete=False,
                state=OnboardingState(),
            )

    def start_conversation(self) -> OnboardingResponse:
        """Generate the opening message"""
        return call_ai_agent(
            client=self.client,
            system_prompt=self.get_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": "Start the onboarding conversation. Greet the user and ask your first question.",
                }
            ],
            response_model=OnboardingResponse,
            max_tokens=2048,
            error_prefix="Onboarding",
        )


# Create router for onboarding endpoints
router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/message")
async def onboarding_message(
    request: OnboardingRequest, client: Anthropic = Depends(get_client)
):
    """Handle onboarding conversation (both start and continuation)

    If conversation_history is empty and latest_message is empty, starts a new conversation.
    Otherwise, continues an existing conversation.
    """
    agent = OnboardingAgent(client)

    # If empty history and no message, this is a start
    if not request.conversation_history and not request.latest_message:
        response = agent.start_conversation()
    else:
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
