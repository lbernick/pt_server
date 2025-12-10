import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from auth import get_or_create_user
from client import get_anthropic_client
from database import get_db
from main import app
from typedefs import Template, TemplateExercise, TrainingPlan
from workout import (
    build_training_plan_prompt,
    convert_db_to_response,
    save_training_plan_to_db,
)


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
    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    # Clean up the override
    app.dependency_overrides.clear()


def test_generate_workout_basic(client, mock_anthropic_client):
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


def test_generate_workout_with_difficulty(client, mock_anthropic_client):
    """Test workout generation with difficulty parameter"""
    workout_request = {"prompt": "leg day", "difficulty": "beginner"}
    response = client.post("/api/v1/generate-workout", json=workout_request)
    assert response.status_code == 200
    data = response.json()

    assert "exercises" in data
    assert len(data["exercises"]) > 0


def test_generate_workout_with_duration(client, mock_anthropic_client):
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


def test_generate_workout_with_all_parameters(client, mock_anthropic_client):
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


def test_generate_workout_missing_prompt(client, mock_anthropic_client):
    """Test that workout generation requires a prompt"""
    workout_request = {}
    response = client.post("/api/v1/generate-workout", json=workout_request)
    assert response.status_code == 422  # Validation error
    # Mock should not be called since validation happens before dependency injection
    assert mock_anthropic_client.messages.create.call_count == 0


def create_mock_training_plan_response():
    """Create a mock training plan response matching the TrainingPlan schema."""
    training_plan_json = {
        "description": (
            "A 3-day strength training program focused on compound movements"
        ),
        "templates": [
            {
                "name": "Upper Body Strength",
                "description": "Focus on compound pressing and pulling movements",
                "exercises": [
                    {"name": "Bench Press", "sets": 4, "rep_min": 6, "rep_max": 8},
                    {"name": "Bent Over Rows", "sets": 4, "rep_min": 8, "rep_max": 10},
                    {"name": "Overhead Press", "sets": 3, "rep_min": 8, "rep_max": 12},
                ],
            },
            {
                "name": "Lower Body Power",
                "description": "Build leg strength with squats and deadlifts",
                "exercises": [
                    {
                        "name": "Back Squat",
                        "sets": 5,
                        "rep_min": 5,
                        "rep_max": 5,
                    },
                    {
                        "name": "Romanian Deadlift",
                        "sets": 3,
                        "rep_min": 8,
                        "rep_max": 10,
                    },
                    {
                        "name": "Leg Press",
                        "sets": 3,
                        "rep_min": 12,
                        "rep_max": 15,
                    },
                ],
            },
            {
                "name": "Upper Body Hypertrophy",
                "description": "Volume work for muscle growth",
                "exercises": [
                    {
                        "name": "Incline Dumbbell Press",
                        "sets": 4,
                        "rep_min": 10,
                        "rep_max": 12,
                    },
                    {
                        "name": "Cable Rows",
                        "sets": 4,
                        "rep_min": 10,
                        "rep_max": 12,
                    },
                    {
                        "name": "Lateral Raises",
                        "sets": 3,
                        "rep_min": 12,
                        "rep_max": 15,
                    },
                ],
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

    app.dependency_overrides[get_anthropic_client] = lambda: mock_client

    yield mock_client

    app.dependency_overrides.clear()


def test_generate_training_plan_basic(client, mock_anthropic_client_training_plan):
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
        # Exercises should be TemplateExercise objects with sets and reps
        for exercise in template["exercises"]:
            assert isinstance(exercise, dict)
            assert "name" in exercise
            assert "sets" in exercise
            assert "rep_min" in exercise
            assert "rep_max" in exercise
            assert isinstance(exercise["name"], str)
            assert isinstance(exercise["sets"], int)
            assert isinstance(exercise["rep_min"], int)
            assert isinstance(exercise["rep_max"], int)
            assert exercise["sets"] > 0
            assert exercise["rep_min"] > 0
            assert exercise["rep_max"] >= exercise["rep_min"]

    # Verify microcycle structure
    assert isinstance(data["microcycle"], list)
    assert len(data["microcycle"]) > 0
    # Microcycle should contain integers (template indices or -1 for rest)
    for day_index in data["microcycle"]:
        assert isinstance(day_index, int)

    # Verify the mock was called
    mock_anthropic_client_training_plan.messages.create.assert_called_once()


def test_generate_training_plan_complete_state(
    client, mock_anthropic_client_training_plan
):
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


def test_generate_training_plan_minimal_state(
    client, mock_anthropic_client_training_plan
):
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


def test_generate_training_plan_with_injuries(
    client, mock_anthropic_client_training_plan
):
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


# Unit tests for helper functions


def test_build_training_plan_prompt():
    """Test building prompt from onboarding state"""
    from typedefs import OnboardingState

    state = OnboardingState(
        fitness_goals=["build strength"],
        experience_level="intermediate",
        days_per_week=4,
        equipment_available=["barbell", "dumbbells"],
        injuries_limitations=["knee pain"],
        preferences="compound movements",
    )

    prompt = build_training_plan_prompt(state)

    assert "build strength" in prompt
    assert "intermediate" in prompt
    assert "4" in prompt
    assert "barbell" in prompt
    assert "knee pain" in prompt
    assert "compound movements" in prompt


# Database integration tests


def test_save_training_plan_to_db(db_session, test_user):
    """Test saving a training plan to the database"""
    # Create a sample training plan (from AI)
    plan = TrainingPlan(
        description="4-day upper/lower split",
        templates=[
            Template(
                name="Upper Body Strength",
                description="Compound pressing and pulling",
                exercises=[
                    TemplateExercise(
                        name="Bench Press", sets=4, rep_min=6, rep_max=8
                    ),
                    TemplateExercise(
                        name="Barbell Rows", sets=4, rep_min=8, rep_max=10
                    ),
                    TemplateExercise(
                        name="Overhead Press", sets=3, rep_min=8, rep_max=12
                    ),
                ],
            ),
            Template(
                name="Lower Body Power",
                description="Leg strength",
                exercises=[
                    TemplateExercise(name="Back Squat", sets=5, rep_min=5, rep_max=5),
                    TemplateExercise(
                        name="Romanian Deadlift", sets=3, rep_min=8, rep_max=10
                    ),
                ],
            ),
        ],
        microcycle=[0, 1, -1, 0, 1, -1, -1],  # Mon, Tue, Rest, Thu, Fri, Rest, Rest
    )

    # Save to database
    db_plan = save_training_plan_to_db(db_session, plan, test_user.id)

    # Verify TrainingPlan was saved
    assert db_plan.id is not None
    assert db_plan.description == "4-day upper/lower split"
    assert db_plan.created_at is not None

    # Verify Templates were saved
    assert len(db_plan.schedule_items) == 7  # 7 days in microcycle

    # Verify ScheduleItems were saved correctly
    schedule_items = db_plan.schedule_items
    assert schedule_items[0].day_index == 0
    assert schedule_items[0].template_id is not None  # Monday - Upper
    assert schedule_items[1].day_index == 1
    assert schedule_items[1].template_id is not None  # Tuesday - Lower
    assert schedule_items[2].day_index == 2
    assert schedule_items[2].template_id is None  # Wednesday - Rest
    assert schedule_items[3].day_index == 3
    assert schedule_items[3].template_id is not None  # Thursday - Upper
    assert schedule_items[4].day_index == 4
    assert schedule_items[4].template_id is not None  # Friday - Lower
    assert schedule_items[5].template_id is None  # Saturday - Rest
    assert schedule_items[6].template_id is None  # Sunday - Rest

    # Verify template references are correct
    upper_template = schedule_items[0].template
    assert upper_template.name == "Upper Body Strength"
    assert upper_template.exercises == [
        {"name": "Bench Press", "sets": 4, "rep_min": 6, "rep_max": 8},
        {"name": "Barbell Rows", "sets": 4, "rep_min": 8, "rep_max": 10},
        {"name": "Overhead Press", "sets": 3, "rep_min": 8, "rep_max": 12},
    ]

    lower_template = schedule_items[1].template
    assert lower_template.name == "Lower Body Power"
    assert lower_template.exercises == [
        {"name": "Back Squat", "sets": 5, "rep_min": 5, "rep_max": 5},
        {"name": "Romanian Deadlift", "sets": 3, "rep_min": 8, "rep_max": 10},
    ]


def test_convert_db_to_response(db_session, test_user):
    """Test converting database model to API response format"""
    # Create test data in database
    plan = TrainingPlan(
        description="3-day full body",
        templates=[
            Template(
                name="Full Body A",
                description="Workout A",
                exercises=[
                    TemplateExercise(name="Squat", sets=5, rep_min=5, rep_max=5),
                    TemplateExercise(name="Bench Press", sets=4, rep_min=8, rep_max=10),
                ],
            ),
            Template(
                name="Full Body B",
                description="Workout B",
                exercises=[
                    TemplateExercise(name="Deadlift", sets=5, rep_min=5, rep_max=5),
                    TemplateExercise(name="Pull-ups", sets=3, rep_min=8, rep_max=12),
                ],
            ),
        ],
        microcycle=[0, -1, 1, -1, 0, -1, -1],
    )

    db_plan = save_training_plan_to_db(db_session, plan, test_user.id)

    # Convert to response format
    response = convert_db_to_response(db_plan)

    # Verify response structure
    assert response.id == db_plan.id
    assert response.description == "3-day full body"
    assert len(response.templates) == 2
    assert response.microcycle == [0, -1, 1, -1, 0, -1, -1]

    # Verify templates in response
    assert response.templates[0].name == "Full Body A"
    assert response.templates[0].exercises == [
        TemplateExercise(name="Squat", sets=5, rep_min=5, rep_max=5),
        TemplateExercise(name="Bench Press", sets=4, rep_min=8, rep_max=10),
    ]
    assert response.templates[0].id is not None

    assert response.templates[1].name == "Full Body B"
    assert response.templates[1].exercises == [
        TemplateExercise(name="Deadlift", sets=5, rep_min=5, rep_max=5),
        TemplateExercise(name="Pull-ups", sets=3, rep_min=8, rep_max=12),
    ]
    assert response.templates[1].id is not None

    # Verify plan timestamps (but not template timestamps)
    assert response.created_at is not None
    assert response.updated_at is not None


def test_training_plan_with_duplicate_templates(db_session, test_user):
    """Test saving a plan where the same template is used multiple days"""
    plan = TrainingPlan(
        description="2-day repeated split",
        templates=[
            Template(
                name="Full Body Workout",
                description="Same workout multiple days",
                exercises=[
                    TemplateExercise(name="Squat", sets=5, rep_min=5, rep_max=5),
                    TemplateExercise(name="Bench", sets=4, rep_min=8, rep_max=10),
                    TemplateExercise(name="Deadlift", sets=3, rep_min=5, rep_max=8),
                ],
            ),
        ],
        microcycle=[0, -1, 0, -1, 0, -1, -1],  # Same workout 3x per week
    )

    db_plan = save_training_plan_to_db(db_session, plan, test_user.id)

    # Verify only ONE template was created
    plan_template_ids = {
        item.template_id for item in db_plan.schedule_items if item.template_id
    }
    assert len(plan_template_ids) == 1

    # Verify schedule items reference the same template
    assert (
        db_plan.schedule_items[0].template_id == db_plan.schedule_items[2].template_id
    )
    assert (
        db_plan.schedule_items[0].template_id == db_plan.schedule_items[4].template_id
    )


def test_get_training_plan_empty_database(client):
    """Test getting training plan when database is empty."""
    response = client.get("/api/v1/training-plan")
    assert response.status_code == 404
    assert response.json()["detail"] == "No training plan found"


def test_get_training_plan_success(client, db_session, test_user):
    """Test getting the most recent training plan."""
    # Create and save a training plan
    plan = TrainingPlan(
        description="Test training plan",
        templates=[
            Template(
                name="Upper Body",
                description="Upper body workout",
                exercises=[
                    TemplateExercise(name="Bench Press", sets=4, rep_min=8, rep_max=10),
                    TemplateExercise(name="Rows", sets=4, rep_min=8, rep_max=10),
                ],
            ),
        ],
        microcycle=[0, -1, 0, -1, 0, -1, -1],
    )

    db_plan = save_training_plan_to_db(db_session, plan, test_user.id)

    # Get the training plan via API
    response = client.get("/api/v1/training-plan")
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["id"] == str(db_plan.id)
    assert data["description"] == "Test training plan"
    assert len(data["templates"]) == 1
    assert data["templates"][0]["name"] == "Upper Body"
    assert data["microcycle"] == [0, -1, 0, -1, 0, -1, -1]
    assert "created_at" in data
    assert "updated_at" in data


def test_get_training_plan_returns_most_recent(client, db_session, test_user):
    """Test that GET /training-plan returns the most recently created plan."""
    from datetime import UTC, datetime, timedelta

    # Create first plan
    plan1 = TrainingPlan(
        description="Older plan",
        templates=[
            Template(
                name="Workout A",
                description="First workout",
                exercises=[
                    TemplateExercise(name="Exercise 1", sets=3, rep_min=10, rep_max=12),
                ],
            ),
        ],
        microcycle=[0, -1, -1, -1, -1, -1, -1],
    )
    db_plan1 = save_training_plan_to_db(db_session, plan1, test_user.id)

    # Manually set created_at to be older
    db_plan1.created_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    # Create second plan (more recent)
    plan2 = TrainingPlan(
        description="Newer plan",
        templates=[
            Template(
                name="Workout B",
                description="Second workout",
                exercises=[
                    TemplateExercise(name="Exercise 2", sets=4, rep_min=8, rep_max=10),
                ],
            ),
        ],
        microcycle=[-1, 0, -1, -1, -1, -1, -1],
    )
    db_plan2 = save_training_plan_to_db(db_session, plan2, test_user.id)

    # Get training plan - should return the newer one
    response = client.get("/api/v1/training-plan")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(db_plan2.id)
    assert data["description"] == "Newer plan"
    assert data["templates"][0]["name"] == "Workout B"


def test_get_next_monday():
    """Test calculating next Monday."""
    from datetime import date

    from workout import get_next_monday

    # Test from a Monday (should return next Monday, 7 days later)
    monday = date(2025, 12, 15)  # Monday, December 15, 2025
    assert get_next_monday(monday) == date(2025, 12, 22)

    # Test from a Tuesday
    tuesday = date(2025, 12, 16)
    assert get_next_monday(tuesday) == date(2025, 12, 22)

    # Test from a Sunday
    sunday = date(2025, 12, 14)
    assert get_next_monday(sunday) == date(2025, 12, 15)

    # Test from a Wednesday (mid-week)
    wednesday = date(2025, 12, 10)
    assert get_next_monday(wednesday) == date(2025, 12, 15)


def test_create_upcoming_workouts_basic(db_session, test_user):
    """Test creating upcoming workouts from a training plan."""
    from datetime import date

    from models import ScheduleItemDB, TemplateDB, TrainingPlanDB
    from workout import create_upcoming_workouts

    # Create templates
    upper = TemplateDB(
        user_id=test_user.id,
        name="Upper Body",
        description="Upper body workout",
        exercises=[{"name": "Bench", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    lower = TemplateDB(
        user_id=test_user.id,
        name="Lower Body",
        description="Lower body workout",
        exercises=[{"name": "Squat", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add_all([upper, lower])
    db_session.flush()

    # Create training plan
    plan = TrainingPlanDB(user_id=test_user.id, description="3-day upper/lower split")
    db_session.add(plan)
    db_session.flush()

    # Create schedule: Upper, Lower, Rest, Upper, Lower, Rest, Rest
    schedule = [
        ScheduleItemDB(training_plan_id=plan.id, day_index=0, template_id=upper.id),
        ScheduleItemDB(training_plan_id=plan.id, day_index=1, template_id=lower.id),
        ScheduleItemDB(
            training_plan_id=plan.id, day_index=2, template_id=None
        ),  # Rest
        ScheduleItemDB(training_plan_id=plan.id, day_index=3, template_id=upper.id),
        ScheduleItemDB(training_plan_id=plan.id, day_index=4, template_id=lower.id),
        ScheduleItemDB(
            training_plan_id=plan.id, day_index=5, template_id=None
        ),  # Rest
        ScheduleItemDB(
            training_plan_id=plan.id, day_index=6, template_id=None
        ),  # Rest
    ]
    db_session.add_all(schedule)
    db_session.commit()
    db_session.refresh(plan)

    # Create workouts for 2 weeks starting from a known Monday
    start_monday = date(2025, 12, 15)  # Monday, December 15, 2025
    workouts = create_upcoming_workouts(
        db_session, plan, num_weeks=2, start_date=start_monday
    )

    # Verify: 2 weeks * 4 workout days per week = 8 workouts
    assert len(workouts) == 8

    # Verify first week pattern: Mon=Upper, Tue=Lower, Wed=Rest, Thu=Upper, Fri=Lower
    assert workouts[0].date == date(2025, 12, 15)  # Monday
    assert workouts[0].template_id == upper.id

    assert workouts[1].date == date(2025, 12, 16)  # Tuesday
    assert workouts[1].template_id == lower.id

    # Wednesday (12/17) is rest - skipped

    assert workouts[2].date == date(2025, 12, 18)  # Thursday
    assert workouts[2].template_id == upper.id

    assert workouts[3].date == date(2025, 12, 19)  # Friday
    assert workouts[3].template_id == lower.id

    # Saturday & Sunday (12/20-21) are rest - skipped

    # Verify second week repeats the pattern
    assert workouts[4].date == date(2025, 12, 22)  # Monday
    assert workouts[4].template_id == upper.id

    # Verify all workouts have no start/end times
    for workout in workouts:
        assert workout.start_time is None
        assert workout.end_time is None
        assert workout.user_id == test_user.id


def test_create_upcoming_workouts_12_weeks(db_session, test_user):
    """Test creating 12 weeks of workouts (default)."""
    from datetime import date, timedelta

    from models import ScheduleItemDB, TemplateDB, TrainingPlanDB
    from workout import create_upcoming_workouts

    # Create single template
    template = TemplateDB(
        user_id=test_user.id,
        name="Full Body",
        description="Full body workout",
        exercises=[{"name": "Squat", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.flush()

    # Create training plan
    plan = TrainingPlanDB(user_id=test_user.id, description="3x per week full body")
    db_session.add(plan)
    db_session.flush()

    # Create schedule: Mon, Wed, Fri workouts; Tue, Thu, Sat, Sun rest
    schedule = [
        ScheduleItemDB(training_plan_id=plan.id, day_index=0, template_id=template.id),
        ScheduleItemDB(training_plan_id=plan.id, day_index=1, template_id=None),
        ScheduleItemDB(training_plan_id=plan.id, day_index=2, template_id=template.id),
        ScheduleItemDB(training_plan_id=plan.id, day_index=3, template_id=None),
        ScheduleItemDB(training_plan_id=plan.id, day_index=4, template_id=template.id),
        ScheduleItemDB(training_plan_id=plan.id, day_index=5, template_id=None),
        ScheduleItemDB(training_plan_id=plan.id, day_index=6, template_id=None),
    ]
    db_session.add_all(schedule)
    db_session.commit()
    db_session.refresh(plan)

    # Create workouts for 12 weeks (default)
    start_monday = date(2026, 1, 5)  # Monday, January 5, 2026
    workouts = create_upcoming_workouts(
        db_session, plan, num_weeks=12, start_date=start_monday
    )

    # Verify: 12 weeks * 3 workout days per week = 36 workouts
    assert len(workouts) == 36

    # Verify first workout is on the start Monday
    assert workouts[0].date == start_monday

    # Verify last workout is within 12 weeks
    last_date = start_monday + timedelta(days=(12 * 7) - 1)
    assert workouts[-1].date <= last_date

    # Verify all use the same template
    for workout in workouts:
        assert workout.template_id == template.id


def test_create_upcoming_workouts_all_rest_days(db_session, test_user):
    """Test plan with all rest days creates no workouts."""
    from datetime import date

    from models import ScheduleItemDB, TrainingPlanDB
    from workout import create_upcoming_workouts

    # Create training plan with all rest days
    plan = TrainingPlanDB(user_id=test_user.id, description="Rest week")
    db_session.add(plan)
    db_session.flush()

    # All rest days
    schedule = [
        ScheduleItemDB(training_plan_id=plan.id, day_index=i, template_id=None)
        for i in range(7)
    ]
    db_session.add_all(schedule)
    db_session.commit()
    db_session.refresh(plan)

    # Create workouts
    workouts = create_upcoming_workouts(
        db_session, plan, num_weeks=2, start_date=date(2025, 12, 15)
    )

    # Should create no workouts
    assert len(workouts) == 0


def test_create_upcoming_workouts_no_schedule_items(db_session, test_user):
    """Test that function raises error if plan has no schedule items."""
    from datetime import date

    import pytest

    from models import TrainingPlanDB
    from workout import create_upcoming_workouts

    # Create training plan without schedule items
    plan = TrainingPlanDB(user_id=test_user.id, description="Empty plan")
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    # Should raise ValueError
    with pytest.raises(ValueError, match="no schedule items"):
        create_upcoming_workouts(
            db_session, plan, num_weeks=1, start_date=date(2025, 12, 15)
        )
