import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import app
from workout import get_client

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
                "exercise": {
                    "name": "Dumbbell Rows",
                    "equipment": {"name": "Dumbbells"},
                },
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
    app.dependency_overrides[get_client] = lambda: mock_client

    yield mock_client

    # Clean up the override
    app.dependency_overrides.clear()


def test_generate_workout_basic(mock_anthropic_client):
    """Test basic workout generation"""
    workout_request = {"prompt": "upper body workout"}
    response = client.post("/api/v1/generate-workout", json=workout_request)
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
    response = client.post("/api/v1/generate-workout", json=workout_request)
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
    response = client.post("/api/v1/generate-workout", json=workout_request)
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
    response = client.post("/api/v1/generate-workout", json=workout_request)
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


def test_generate_workout_missing_prompt(mock_anthropic_client):
    """Test that workout generation requires a prompt"""
    workout_request = {}
    response = client.post("/api/v1/generate-workout", json=workout_request)
    assert response.status_code == 422  # Validation error
    # Mock should not be called since validation happens before dependency injection
    assert mock_anthropic_client.messages.create.call_count == 0


def create_mock_training_plan_response():
    """Create a mock training plan response matching the TrainingPlan schema."""
    training_plan_json = {
        "description": "A 3-day strength training program focused on compound movements",
        "templates": [
            {
                "name": "Upper Body Strength",
                "description": "Focus on compound pressing and pulling movements",
                "exercises": ["Bench Press", "Bent Over Rows", "Overhead Press"],
            },
            {
                "name": "Lower Body Power",
                "description": "Build leg strength with squats and deadlifts",
                "exercises": ["Back Squat", "Romanian Deadlift", "Leg Press"],
            },
            {
                "name": "Upper Body Hypertrophy",
                "description": "Volume work for muscle growth",
                "exercises": ["Incline Dumbbell Press", "Cable Rows", "Lateral Raises"],
            },
        ],
        "microcycle": [
            0,
            -1,
            1,
            -1,
            2,
            -1,
            -1,
        ],  # Mon: template 0, Wed: template 1, Fri: template 2, -1 = rest day
    }
    return json.dumps(training_plan_json)


@pytest.fixture
def mock_anthropic_client_training_plan():
    """Fixture for mocking training plan generation."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text=create_mock_training_plan_response())]
    mock_client.messages.create.return_value = mock_response

    app.dependency_overrides[get_client] = lambda: mock_client

    yield mock_client

    app.dependency_overrides.clear()


def test_generate_training_plan_basic(mock_anthropic_client_training_plan):
    """Test basic training plan generation with minimal onboarding state"""
    onboarding_state = {
        "fitness_goals": ["build strength"],
        "experience_level": "intermediate",
        "current_routine": None,
        "days_per_week": 3,
        "equipment_available": ["barbell", "dumbbells"],
        "injuries_limitations": [],
        "preferences": None,
    }
    response = client.post("/api/v1/generate-training-plan", json=onboarding_state)
    assert response.status_code == 200
    data = response.json()

    # Verify the response has the TrainingPlan structure
    assert "description" in data
    assert "templates" in data
    assert "microcycle" in data

    # Verify description is a string
    assert isinstance(data["description"], str)
    assert len(data["description"]) > 0

    # Verify templates structure
    assert isinstance(data["templates"], list)
    assert len(data["templates"]) > 0

    for template in data["templates"]:
        assert "name" in template
        assert "exercises" in template
        assert isinstance(template["name"], str)
        assert isinstance(template["exercises"], list)
        assert len(template["exercises"]) > 0
        # Exercises should be strings (exercise names)
        for exercise in template["exercises"]:
            assert isinstance(exercise, str)

    # Verify microcycle structure
    assert isinstance(data["microcycle"], list)
    assert len(data["microcycle"]) > 0
    # Microcycle should contain integers (template indices or -1 for rest)
    for day_index in data["microcycle"]:
        assert isinstance(day_index, int)

    # Verify the mock was called
    mock_anthropic_client_training_plan.messages.create.assert_called_once()


def test_generate_training_plan_complete_state(mock_anthropic_client_training_plan):
    """Test training plan generation with complete onboarding state"""
    onboarding_state = {
        "fitness_goals": ["build strength", "muscle gain"],
        "experience_level": "intermediate",
        "current_routine": "3 day split, mainly compound lifts",
        "days_per_week": 4,
        "equipment_available": ["barbell", "dumbbells", "squat rack", "bench"],
        "injuries_limitations": ["previous knee injury"],
        "preferences": "enjoys compound lifts",
    }
    response = client.post("/api/v1/generate-training-plan", json=onboarding_state)
    assert response.status_code == 200
    data = response.json()

    # Verify basic structure
    assert "description" in data
    assert "templates" in data
    assert "microcycle" in data

    # Verify templates contain workout information
    assert len(data["templates"]) > 0
    assert len(data["microcycle"]) > 0

    # Verify mock was called with correct parameters
    mock_anthropic_client_training_plan.messages.create.assert_called_once()
    call_args = mock_anthropic_client_training_plan.messages.create.call_args

    # Verify the prompt includes the onboarding information
    user_message = call_args[1]["messages"][0]["content"]
    assert "build strength" in user_message
    assert "intermediate" in user_message
    assert "4" in user_message


def test_generate_training_plan_minimal_state(mock_anthropic_client_training_plan):
    """Test training plan generation with minimal onboarding state"""
    onboarding_state = {
        "fitness_goals": ["general fitness"],
        "experience_level": None,
        "current_routine": None,
        "days_per_week": None,
        "equipment_available": None,
        "injuries_limitations": None,
        "preferences": None,
    }
    response = client.post("/api/v1/generate-training-plan", json=onboarding_state)
    assert response.status_code == 200
    data = response.json()

    # Should still return a valid training plan structure
    assert "description" in data
    assert "templates" in data
    assert "microcycle" in data

    # Verify mock was called
    mock_anthropic_client_training_plan.messages.create.assert_called_once()


def test_generate_training_plan_with_injuries(mock_anthropic_client_training_plan):
    """Test training plan generation respects injuries and limitations"""
    onboarding_state = {
        "fitness_goals": ["weight loss"],
        "experience_level": "beginner",
        "current_routine": None,
        "days_per_week": 3,
        "equipment_available": ["dumbbells"],
        "injuries_limitations": ["lower back pain", "shoulder impingement"],
        "preferences": "low impact exercises",
    }
    response = client.post("/api/v1/generate-training-plan", json=onboarding_state)
    assert response.status_code == 200
    data = response.json()

    # Verify the structure
    assert "description" in data
    assert "templates" in data
    assert "microcycle" in data

    # Verify mock was called and injuries were included in prompt
    mock_anthropic_client_training_plan.messages.create.assert_called_once()
    call_args = mock_anthropic_client_training_plan.messages.create.call_args
    user_message = call_args[1]["messages"][0]["content"]
    assert "lower back pain" in user_message
    assert "shoulder impingement" in user_message
