from typing import List

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_utils import call_ai_agent
from auth import AuthenticatedUser, get_or_create_user
from client import get_anthropic_client
from database import get_db
from models import UserDB
from typedefs import OnboardingRequest, OnboardingResponse, OnboardingState


def merge_onboarding_states(
    old_state: OnboardingState | None,
    new_state: OnboardingState,
) -> OnboardingState:
    """Merge old and new onboarding states intelligently.

    Preserves information from old state when new state has None values,
    allowing the LLM to "remember" previously collected information even
    if it doesn't include those fields in the current response.

    Args:
        old_state: Previously saved state from database (or None for first save)
        new_state: New state from LLM response

    Returns:
        Merged OnboardingState with best information from both

    Examples:
        >>> old = OnboardingState(fitness_goals=["strength"], days_per_week=4)
        >>> new = OnboardingState(
        ...     fitness_goals=["strength", "cardio"],
        ...     days_per_week=None
        ... )
        >>> merged = merge_onboarding_states(old, new)
        >>> merged.fitness_goals
        ["strength", "cardio"]
        >>> merged.days_per_week
        4
    """
    if old_state is None:
        return new_state

    # Helper to choose between old and new values
    def choose_value(new_val, old_val):
        """Use new value if not None, otherwise preserve old value."""
        return new_val if new_val is not None else old_val

    return OnboardingState(
        fitness_goals=choose_value(new_state.fitness_goals, old_state.fitness_goals),
        experience_level=choose_value(
            new_state.experience_level, old_state.experience_level
        ),
        current_routine=choose_value(
            new_state.current_routine, old_state.current_routine
        ),
        days_per_week=choose_value(new_state.days_per_week, old_state.days_per_week),
        equipment_available=choose_value(
            new_state.equipment_available, old_state.equipment_available
        ),
        injuries_limitations=choose_value(
            new_state.injuries_limitations, old_state.injuries_limitations
        ),
        preferences=choose_value(new_state.preferences, old_state.preferences),
    )


def has_any_data(state: OnboardingState) -> bool:
    """Check if state contains any non-None values.

    Args:
        state: OnboardingState to check

    Returns:
        True if at least one field has a value, False otherwise
    """
    return any(
        [
            state.fitness_goals,
            state.experience_level,
            state.current_routine,
            state.days_per_week is not None,
            state.equipment_available,
            state.injuries_limitations,
            state.preferences,
        ]
    )


def format_state_for_prompt(state: OnboardingState) -> str:
    """Format state into human-readable text for system prompt.

    Args:
        state: OnboardingState to format

    Returns:
        Human-readable text summarizing the state
    """
    parts = []

    if state.fitness_goals:
        parts.append(f"Goals: {', '.join(state.fitness_goals)}")

    if state.experience_level:
        parts.append(f"Experience: {state.experience_level}")

    if state.current_routine:
        parts.append(f"Current Routine: {state.current_routine}")

    if state.days_per_week is not None:
        parts.append(f"Training Days: {state.days_per_week} per week")

    if state.equipment_available:
        parts.append(f"Equipment: {', '.join(state.equipment_available)}")

    if state.injuries_limitations:
        parts.append(f"Limitations: {', '.join(state.injuries_limitations)}")

    if state.preferences:
        parts.append(f"Preferences: {state.preferences}")

    return "\n".join(parts) if parts else "No information collected yet"


class OnboardingAgent:
    def __init__(self, client: Anthropic):
        self.client = client

    def get_system_prompt(self, previous_state: OnboardingState | None = None) -> str:
        """Generate system prompt, optionally with resume context.

        Args:
            previous_state: Previously saved onboarding state for resume context

        Returns:
            System prompt string with resume instructions if applicable
        """
        base_prompt = """You are an expert fitness coach conducting an intake interview
with a new client.

Your goal is to gather enough information to create a personalized
12-week workout plan. You need to understand:

1. FITNESS GOALS
   - What they want to achieve (strength, muscle gain, weight loss,
     athletic performance, general fitness)
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
    "fitness_goals": ["list", "of", "goals", "in", "priority", "order"],
    // null if not yet known
    "experience_level": "description of current fitness and experience level",
    // null if not yet known
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

        # Add resume context if previous state exists
        if previous_state and has_any_data(previous_state):
            state_summary = format_state_for_prompt(previous_state)
            base_prompt += f"""

PREVIOUSLY COLLECTED INFORMATION:
{state_summary}

The user is returning to continue or update their onboarding.
- Welcome them back and briefly acknowledge what you already know
- Ask if they want to review/update any existing information
- If information is complete, ask if they're ready to generate their plan
- If information is incomplete, continue gathering the missing details
- Always include previously collected information in your state response"""

        return base_prompt

    def process_message(
        self,
        conversation_history: List[dict],
        latest_message: str,
        previous_state: OnboardingState | None = None,
    ) -> OnboardingResponse:
        """Process user's message and determine next question.

        Args:
            conversation_history: Full conversation history
            latest_message: User's latest message
            previous_state: Previously saved state for context

        Returns:
            OnboardingResponse with next message and updated state
        """
        # Add latest message to history
        messages = conversation_history + [{"role": "user", "content": latest_message}]

        try:
            return call_ai_agent(
                client=self.client,
                system_prompt=self.get_system_prompt(previous_state),
                messages=messages,
                response_model=OnboardingResponse,
                max_tokens=2048,
                error_prefix="Onboarding",
            )
        except Exception:
            # Fallback if parsing fails
            return OnboardingResponse(
                message=(
                    "I'm having trouble processing that. "
                    "Could you tell me a bit about your fitness goals?"
                ),
                is_complete=False,
                state=OnboardingState(),
            )

    def start_conversation(
        self, previous_state: OnboardingState | None = None
    ) -> OnboardingResponse:
        """Generate the opening message.

        Args:
            previous_state: Previously saved state for resume context

        Returns:
            OnboardingResponse with opening/welcome-back message
        """
        return call_ai_agent(
            client=self.client,
            system_prompt=self.get_system_prompt(previous_state),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Start the onboarding conversation. "
                        "Greet the user and ask your first question."
                    ),
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
    request: OnboardingRequest,
    client: Anthropic = Depends(get_anthropic_client),
    user: AuthenticatedUser = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Handle onboarding conversation with incremental persistence.

    This endpoint:
    1. Loads any previously saved onboarding state from the database
    2. Processes the user's message with the AI agent (providing context)
    3. Merges the new LLM response with saved state (preserving information)
    4. Saves the merged state back to the database
    5. Returns the response with the current merged state

    The merge ensures that information isn't lost if the LLM forgets to
    include previously collected fields in its response.

    Requires authentication via Firebase token.
    """
    agent = OnboardingAgent(client)

    # Load saved onboarding state from database
    db_user = db.query(UserDB).filter(UserDB.id == user.user_id).first()
    saved_state = None

    if db_user and db_user.onboarding_data:
        try:
            saved_state = OnboardingState(**db_user.onboarding_data)
        except Exception as e:
            # Log parse error but continue (treat as no saved state)
            print(f"Error parsing saved onboarding state: {e}")
            saved_state = None

    # Generate AI response (with context if resuming)
    if not request.conversation_history and not request.latest_message:
        # Starting new or resuming - provide previous state context
        response = agent.start_conversation(previous_state=saved_state)
    else:
        # Continuing conversation - provide previous state context
        response = agent.process_message(
            conversation_history=request.conversation_history,
            latest_message=request.latest_message,
            previous_state=saved_state,
        )

    # Merge old and new states to preserve information
    merged_state = merge_onboarding_states(saved_state, response.state)

    # Save merged state back to database
    try:
        db_user.onboarding_data = merged_state.model_dump(mode="json")
        db.commit()
    except Exception as e:
        db.rollback()
        # Log error but don't fail the request
        # The LLM response is still valid for the client
        print(f"Failed to save onboarding state: {e}")

    # Return response with merged state (not raw LLM state)
    return OnboardingResponse(
        message=response.message,
        is_complete=response.is_complete,
        state=merged_state,
    )
