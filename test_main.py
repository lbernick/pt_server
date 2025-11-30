import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import app, get_anthropic_client

client = TestClient(app)


def create_mock_workout_response():
    """Create a mock workout response matching the Workout schema."""
    workout_json = {
        "exercises": [
            {
                "exercise": {"name": "Push-ups", "equipment": {"name": "None"}},
                "sets": [
                    {"reps": 10, "weight": None, "rest_seconds": 60},
                    {"reps": 10, "weight": None, "rest_seconds": 60},
                    {"reps": 10, "weight": None, "rest_seconds": 60},
                ],
            },
            {
                "exercise": {"name": "Dumbbell Rows", "equipment": {"name": "Dumbbells"}},
                "sets": [
                    {"reps": 12, "weight": 25.0, "rest_seconds": 90},
                    {"reps": 12, "weight": 25.0, "rest_seconds": 90},
                ],
            },
        ]
    }
    return json.dumps(workout_json)


@pytest.fixture
def mock_anthropic_client():
    """Fixture that provides a mocked Anthropic client and automatically cleans up."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_workout_response())]
    mock_client.messages.create.return_value = mock_response

    # Override the dependency
    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    # Clean up the override
    app.dependency_overrides.clear()


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to PT Server"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_generate_workout_basic(mock_anthropic_client):
    """Test basic workout generation"""
    workout_request = {"prompt": "upper body workout"}
    response = client.post("/generate-workout", json=workout_request)
    assert response.status_code == 200
    data = response.json()

    # Verify the response has the Workout structure
    assert "exercises" in data
    assert isinstance(data["exercises"], list)
    assert len(data["exercises"]) > 0

    # Verify first exercise structure
    first_exercise = data["exercises"][0]
    assert "exercise" in first_exercise
    assert "sets" in first_exercise
    assert "name" in first_exercise["exercise"]
    assert "equipment" in first_exercise["exercise"]
    assert isinstance(first_exercise["sets"], list)

    # Verify first set structure
    if len(first_exercise["sets"]) > 0:
        first_set = first_exercise["sets"][0]
        assert "reps" in first_set
        assert isinstance(first_set["reps"], int)

    # Verify the mock was called
    mock_anthropic_client.messages.create.assert_called_once()


def test_generate_workout_with_difficulty(mock_anthropic_client):
    """Test workout generation with difficulty parameter"""
    workout_request = {"prompt": "leg day", "difficulty": "beginner"}
    response = client.post("/generate-workout", json=workout_request)
    assert response.status_code == 200
    data = response.json()

    assert "exercises" in data
    assert len(data["exercises"]) > 0


def test_generate_workout_with_duration(mock_anthropic_client):
    """Test workout generation with duration parameter"""
    workout_request = {
        "prompt": "full body workout",
        "duration_minutes": 30,
    }
    response = client.post("/generate-workout", json=workout_request)
    assert response.status_code == 200
    data = response.json()

    assert "exercises" in data
    assert len(data["exercises"]) > 0


def test_generate_workout_with_all_parameters(mock_anthropic_client):
    """Test workout generation with all optional parameters"""
    workout_request = {
        "prompt": "cardio and strength",
        "difficulty": "intermediate",
        "duration_minutes": 45,
    }
    response = client.post("/generate-workout", json=workout_request)
    assert response.status_code == 200
    data = response.json()

    assert "exercises" in data
    assert len(data["exercises"]) > 0

    # Verify exercise details
    for workout_exercise in data["exercises"]:
        assert "exercise" in workout_exercise
        assert "name" in workout_exercise["exercise"]
        assert "equipment" in workout_exercise["exercise"]
        assert "name" in workout_exercise["exercise"]["equipment"]
        assert "sets" in workout_exercise
        assert len(workout_exercise["sets"]) > 0


def test_generate_workout_missing_prompt():
    """Test that workout generation requires a prompt"""
    workout_request = {}
    response = client.post("/generate-workout", json=workout_request)
    assert response.status_code == 422  # Validation error
