import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from auth import get_or_create_user
from client import get_anthropic_client
from database import get_db
from main import app
from onboarding import merge_onboarding_states
from typedefs import OnboardingState


@pytest.fixture
def client(db_session, test_authenticated_user, mock_firebase_auth):
    """Create test client with database and auth overrides."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_auth():
        return test_authenticated_user

    # Mock Firebase token verification
    mock_firebase_auth.verify_id_token.return_value = {
        "uid": test_authenticated_user.firebase_uid,
        "email": test_authenticated_user.email,
        "email_verified": True,
    }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_or_create_user] = override_auth

    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()


def create_mock_onboarding_start_response():
    """Create a mock response for starting onboarding."""
    response_json = {
        "message": (
            "Hi! I'm excited to help you create a personalized workout plan. "
            "Let's start by understanding your fitness goals. What are you "
            "hoping to achieve with your training?"
        ),
        "is_complete": False,
        "state": {
            "fitness_goals": None,
            "experience_level": None,
            "current_routine": None,
            "days_per_week": None,
            "equipment_available": None,
            "injuries_limitations": None,
            "preferences": None,
        },
    }
    return json.dumps(response_json)


def create_mock_onboarding_message_response():
    """Create a mock response for continuing onboarding."""
    response_json = {
        "message": (
            "Great! Building strength is a solid goal. How much experience "
            "do you have with strength training?"
        ),
        "is_complete": False,
        "state": {
            "fitness_goals": ["build strength"],
            "experience_level": None,
            "current_routine": None,
            "days_per_week": None,
            "equipment_available": None,
            "injuries_limitations": None,
            "preferences": None,
        },
    }
    return json.dumps(response_json)


def create_mock_onboarding_complete_response():
    """Create a mock response when onboarding is complete."""
    response_json = {
        "message": (
            "Perfect! I have all the information I need to create your "
            "personalized workout plan. You're looking to build strength as "
            "an intermediate lifter, training 4 days per week for 60 minutes "
            "with full gym access. Let me create your plan!"
        ),
        "is_complete": True,
        "state": {
            "fitness_goals": ["build strength", "muscle gain"],
            "experience_level": "intermediate",
            "current_routine": "3 day split, mainly compound lifts",
            "days_per_week": 4,
            "equipment_available": ["barbell", "dumbbells", "squat rack", "bench"],
            "injuries_limitations": [],
            "preferences": "enjoys_compound_lifts",
        },
    }
    return json.dumps(response_json)


@pytest.fixture
def mock_anthropic_client_start():
    """Fixture for mocking start conversation."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_onboarding_start_response())]
    mock_client.messages.create.return_value = mock_response

    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_anthropic_client_message():
    """Fixture for mocking message conversation."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_onboarding_message_response())]
    mock_client.messages.create.return_value = mock_response

    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_anthropic_client_complete():
    """Fixture for mocking complete conversation."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_onboarding_complete_response())]
    mock_client.messages.create.return_value = mock_response

    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    app.dependency_overrides.clear()


def test_start_onboarding(client, mock_anthropic_client_start):
    """Test starting the onboarding conversation with empty request"""
    # Empty request to trigger start
    response = client.post("/api/v1/onboarding/message", json={})
    assert response.status_code == 200
    data = response.json()

    # Verify the onboarding response
    assert "message" in data
    assert "is_complete" in data
    assert "state" in data

    assert data["is_complete"] is False
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0

    # Verify state structure
    state = data["state"]
    assert "fitness_goals" in state
    assert "experience_level" in state
    assert "days_per_week" in state

    # Verify mock was called
    mock_anthropic_client_start.messages.create.assert_called_once()


def test_onboarding_message_basic(client, mock_anthropic_client_message):
    """Test continuing onboarding conversation"""
    request_data = {
        "conversation_history": [
            {
                "role": "assistant",
                "content": "Hi! What are your fitness goals?",
            },
        ],
        "latest_message": "I want to build strength",
    }

    response = client.post("/api/v1/onboarding/message", json=request_data)
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "message" in data
    assert "is_complete" in data
    assert "state" in data

    assert data["is_complete"] is False
    assert isinstance(data["message"], str)

    # Verify state is being updated
    state = data["state"]
    assert state["fitness_goals"] == ["build strength"]

    # Verify mock was called
    mock_anthropic_client_message.messages.create.assert_called_once()


def test_onboarding_message_with_complete_state(client, mock_anthropic_client_complete):
    """Test onboarding conversation that completes"""
    request_data = {
        "conversation_history": [
            {"role": "assistant", "content": "What are your goals?"},
            {"role": "user", "content": "Build strength"},
            {
                "role": "assistant",
                "content": "How many days can you train?",
            },
            {"role": "user", "content": "4 days per week"},
        ],
        "latest_message": "I have full gym access",
    }

    response = client.post("/api/v1/onboarding/message", json=request_data)
    assert response.status_code == 200
    data = response.json()

    # Verify completion
    assert data["is_complete"] is True
    assert isinstance(data["message"], str)

    # Verify state is complete
    state = data["state"]
    assert state["fitness_goals"] is not None
    assert state["experience_level"] is not None
    assert state["days_per_week"] is not None
    assert state["equipment_available"] is not None

    # Verify mock was called
    mock_anthropic_client_complete.messages.create.assert_called_once()


def test_onboarding_message_with_history_but_no_message(
    client, mock_anthropic_client_start
):
    """Test that providing history but no message still works (treated as start)"""
    # History provided but empty message - should treat as continuation
    # with empty message
    request_data = {"conversation_history": [], "latest_message": ""}
    response = client.post("/api/v1/onboarding/message", json=request_data)
    assert response.status_code == 200

    # Should call start_conversation since both are empty
    mock_anthropic_client_start.messages.create.assert_called_once()


# Unit tests for merge logic
def test_merge_none_old_state():
    """When old state is None, return new state as-is."""
    new = OnboardingState(fitness_goals=["strength"])
    result = merge_onboarding_states(None, new)
    assert result.fitness_goals == ["strength"]


def test_merge_preserves_old_when_new_is_none():
    """When new field is None, preserve old field value."""
    old = OnboardingState(fitness_goals=["strength"], days_per_week=4)
    new = OnboardingState(fitness_goals=["strength"], days_per_week=None)

    result = merge_onboarding_states(old, new)

    assert result.fitness_goals == ["strength"]
    assert result.days_per_week == 4  # Preserved from old


def test_merge_updates_when_new_has_value():
    """When new field has value, use it (even if different from old)."""
    old = OnboardingState(experience_level="beginner")
    new = OnboardingState(experience_level="intermediate")

    result = merge_onboarding_states(old, new)

    assert result.experience_level == "intermediate"


def test_merge_empty_list_is_valid():
    """Empty list [] is a valid value, not None."""
    old = OnboardingState(injuries_limitations=["knee pain"])
    new = OnboardingState(injuries_limitations=[])  # User says no limitations

    result = merge_onboarding_states(old, new)

    assert result.injuries_limitations == []  # Use new empty list


def test_merge_all_fields():
    """Test merging all fields simultaneously."""
    old = OnboardingState(
        fitness_goals=["strength"],
        experience_level="beginner",
        current_routine=None,
        days_per_week=3,
        equipment_available=None,
        injuries_limitations=["knee"],
        preferences=None,
    )

    new = OnboardingState(
        fitness_goals=["strength", "muscle"],  # Updated
        experience_level=None,  # Forgot
        current_routine="PPL split",  # New info
        days_per_week=4,  # Updated
        equipment_available=["barbell"],  # New info
        injuries_limitations=None,  # Forgot
        preferences=None,  # Still unknown
    )

    result = merge_onboarding_states(old, new)

    assert result.fitness_goals == ["strength", "muscle"]
    assert result.experience_level == "beginner"  # Preserved
    assert result.current_routine == "PPL split"
    assert result.days_per_week == 4
    assert result.equipment_available == ["barbell"]
    assert result.injuries_limitations == ["knee"]  # Preserved
    assert result.preferences is None


# Integration tests for persistence
def test_onboarding_persistence_on_first_message(
    client, mock_anthropic_client_message, db_session
):
    """Test that onboarding state is saved to database on first message."""
    from models import UserDB

    request_data = {
        "conversation_history": [],
        "latest_message": "I want to build strength",
    }

    response = client.post("/api/v1/onboarding/message", json=request_data)
    assert response.status_code == 200

    # Verify state was saved to database
    user = db_session.query(UserDB).first()
    assert user.onboarding_data is not None
    assert user.onboarding_data["fitness_goals"] == ["build strength"]


def test_onboarding_resume_loads_previous_state(
    client, mock_anthropic_client_start, db_session
):
    """Test that resuming onboarding loads previous state."""
    from models import UserDB

    # Setup: User has partial onboarding data
    user = db_session.query(UserDB).first()
    user.onboarding_data = {
        "fitness_goals": ["strength"],
        "experience_level": "intermediate",
        "current_routine": None,
        "days_per_week": None,
        "equipment_available": None,
        "injuries_limitations": None,
        "preferences": None,
    }
    db_session.commit()

    # Resume with empty request
    response = client.post("/api/v1/onboarding/message", json={})
    assert response.status_code == 200

    data = response.json()
    # Should return saved state in response
    assert data["state"]["fitness_goals"] == ["strength"]
    assert data["state"]["experience_level"] == "intermediate"


def test_onboarding_merge_preserves_forgotten_fields(client, db_session):
    """Test that merge preserves fields LLM forgot to include."""
    from models import UserDB

    # Setup: User has existing data
    user = db_session.query(UserDB).first()
    user.onboarding_data = {
        "fitness_goals": ["strength"],
        "experience_level": "intermediate",
        "current_routine": "PPL",
        "days_per_week": 4,
        "equipment_available": ["barbell"],
        "injuries_limitations": [],
        "preferences": "compound lifts",
    }
    db_session.commit()

    # Mock LLM response that "forgets" some fields
    mock_response_json = {
        "message": "Tell me more about your goals",
        "is_complete": False,
        "state": {
            "fitness_goals": ["strength", "hypertrophy"],  # Updated
            "experience_level": None,  # Forgot
            "current_routine": None,  # Forgot
            "days_per_week": 5,  # Updated
            "equipment_available": None,  # Forgot
            "injuries_limitations": None,  # Forgot
            "preferences": None,  # Forgot
        },
    }

    from client import get_anthropic_client
    from main import app

    mock_client = Mock()
    mock_anthropic_response = Mock()
    mock_anthropic_response.content = [Mock(text=json.dumps(mock_response_json))]
    mock_client.messages.create.return_value = mock_anthropic_response

    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    request_data = {
        "conversation_history": [{"role": "assistant", "content": "Hi"}],
        "latest_message": "I want to add hypertrophy",
    }

    response = client.post("/api/v1/onboarding/message", json=request_data)
    assert response.status_code == 200

    data = response.json()
    # Verify merged state preserves forgotten fields
    assert data["state"]["fitness_goals"] == ["strength", "hypertrophy"]
    assert data["state"]["experience_level"] == "intermediate"  # Preserved!
    assert data["state"]["current_routine"] == "PPL"  # Preserved!
    assert data["state"]["days_per_week"] == 5
    assert data["state"]["equipment_available"] == ["barbell"]  # Preserved!
    assert data["state"]["preferences"] == "compound lifts"  # Preserved!

    # Verify it was saved to DB
    db_session.refresh(user)
    assert user.onboarding_data["experience_level"] == "intermediate"

    app.dependency_overrides.clear()
