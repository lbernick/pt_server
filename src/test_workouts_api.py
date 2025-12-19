"""Tests for workout CRUD API endpoints."""

from datetime import date, datetime
from uuid import uuid4

import pytest
from deepdiff import DeepDiff
from fastapi.testclient import TestClient

from auth import get_or_create_user
from database import get_db
from main import app
from models import WorkoutDB


def assert_exercises_equal(
    actual: list[dict],
    expected: list[dict],
    message: str = "Exercises do not match",
) -> None:
    """Assert that two exercise lists are identical using deepdiff.

    Provides clear diff output when assertions fail, making it easy to identify
    what changed unexpectedly.

    Args:
        actual: The actual exercises from API response
        expected: The expected exercises structure
        message: Custom message to show on assertion failure

    Raises:
        AssertionError: If exercises differ, with detailed diff output
    """
    diff = DeepDiff(expected, actual, ignore_order=False)
    assert not diff, f"{message}\n\nDifferences found:\n{diff.pretty()}"


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


@pytest.fixture
def sample_workout(db_session, test_user):
    """Create a sample workout in the database."""
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 11, 30),
        start_time=datetime(2025, 11, 30, 9, 0, 0),
        end_time=datetime(2025, 11, 30, 10, 30, 0),
    )
    db_session.add(workout)
    db_session.commit()
    db_session.refresh(workout)
    return workout


@pytest.fixture
def unfinished_workout(db_session, test_user):
    """Create an unfinished workout (not yet finished) in the database."""
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 11, 30),
        start_time=datetime(2025, 11, 30, 9, 0, 0),
        end_time=None,
    )
    db_session.add(workout)
    db_session.commit()
    db_session.refresh(workout)
    return workout


def test_create_workout(client):
    """Test creating a new workout."""
    response = client.post(
        "/api/v1/workouts",
        json={
            "date": "2025-12-01",
            "start_time": "2025-12-01T09:00:00",
            "end_time": "2025-12-01T10:30:00",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2025-12-01"
    assert data["start_time"] == "2025-12-01T09:00:00"
    assert data["end_time"] == "2025-12-01T10:30:00"
    assert "id" in data


def test_create_workout_minimal(client):
    """Test creating a workout with only required fields."""
    response = client.post(
        "/api/v1/workouts",
        json={"date": "2025-12-01"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2025-12-01"
    assert data["start_time"] is None
    assert data["end_time"] is None


def test_list_workouts_empty(client):
    """Test listing workouts when database is empty."""
    response = client.get("/api/v1/workouts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_workouts(client, sample_workout):
    """Test listing workouts."""
    response = client.get("/api/v1/workouts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(sample_workout.id)
    assert data[0]["date"] == "2025-11-30"


def test_list_workouts_pagination(client, db_session, test_user):
    """Test workout pagination."""
    # Create multiple workouts
    for i in range(5):
        workout = WorkoutDB(user_id=test_user.id, date=date(2025, 11, 20 + i))
        db_session.add(workout)
    db_session.commit()

    # Test skip and limit
    response = client.get("/api/v1/workouts?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_workouts_by_date(client, db_session, test_user):
    """Test filtering workouts by date."""
    # Create workouts on different dates
    workout1 = WorkoutDB(user_id=test_user.id, date=date(2025, 12, 9))
    workout2 = WorkoutDB(user_id=test_user.id, date=date(2025, 12, 9))
    workout3 = WorkoutDB(user_id=test_user.id, date=date(2025, 12, 10))
    db_session.add_all([workout1, workout2, workout3])
    db_session.commit()

    # Filter by specific date
    response = client.get("/api/v1/workouts?date=2025-12-09")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(w["date"] == "2025-12-09" for w in data)

    # Filter by different date
    response = client.get("/api/v1/workouts?date=2025-12-10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["date"] == "2025-12-10"

    # No date filter returns all
    response = client.get("/api/v1/workouts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_get_todays_workouts(client, db_session, test_user):
    """Test getting today's workouts."""
    today = date.today()

    # Create workout for today
    workout_today = WorkoutDB(user_id=test_user.id, date=today)
    db_session.add(workout_today)
    db_session.commit()

    # Get today's workouts
    response = client.get(f"/api/v1/workouts?date={today.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["date"] == today.isoformat()


def test_get_workout(client, sample_workout):
    """Test getting a specific workout."""
    response = client.get(f"/api/v1/workouts/{sample_workout.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_workout.id)
    assert data["date"] == "2025-11-30"
    assert data["start_time"] == "2025-11-30T09:00:00"
    assert data["end_time"] == "2025-11-30T10:30:00"


def test_get_workout_not_found(client):
    """Test getting a non-existent workout."""
    fake_id = uuid4()
    response = client.get(f"/api/v1/workouts/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


def test_update_workout(client, unfinished_workout):
    """Test updating a workout."""
    response = client.patch(
        f"/api/v1/workouts/{unfinished_workout.id}",
        json={
            "date": "2025-12-05",
            "start_time": "2025-12-05T14:00:00",
            "end_time": "2025-12-05T15:30:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(unfinished_workout.id)
    assert data["date"] == "2025-12-05"
    assert data["start_time"] == "2025-12-05T14:00:00"
    assert data["end_time"] == "2025-12-05T15:30:00"


def test_update_workout_partial(client, unfinished_workout):
    """Test partially updating a workout."""
    response = client.patch(
        f"/api/v1/workouts/{unfinished_workout.id}",
        json={"date": "2025-12-10"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2025-12-10"
    # Original start time should be preserved, end_time should still be None
    assert data["start_time"] == "2025-11-30T09:00:00"
    assert data["end_time"] is None


def test_update_workout_not_found(client):
    """Test updating a non-existent workout."""
    fake_id = uuid4()
    response = client.patch(
        f"/api/v1/workouts/{fake_id}",
        json={"date": "2025-12-05"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


def test_update_workout_already_finished(client, db_session, test_user):
    """Test that updating a finished workout fails."""
    from models import WorkoutDB

    # Create finished workout
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
        end_time=datetime(2025, 12, 20, 10, 30, 0),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to update it
    response = client.patch(
        f"/api/v1/workouts/{workout_id}",
        json={"date": "2025-12-21"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot modify a finished workout"


def test_delete_workout(client, sample_workout):
    """Test deleting a workout."""
    workout_id = sample_workout.id
    response = client.delete(f"/api/v1/workouts/{workout_id}")
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/api/v1/workouts/{workout_id}")
    assert response.status_code == 404


def test_delete_workout_not_found(client):
    """Test deleting a non-existent workout."""
    fake_id = uuid4()
    response = client.delete(f"/api/v1/workouts/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


def test_workout_with_template_relationship(db_session, test_user):
    """Test that a workout can optionally reference a template."""
    from datetime import date

    from models import TemplateDB, WorkoutDB

    # Create a template
    template = TemplateDB(
        user_id=test_user.id,
        name="Upper Body",
        description="Test template",
        exercises=[{"name": "Bench Press", "sets": 4, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    # Create workout WITH template
    workout_with_template = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 9),
    )
    db_session.add(workout_with_template)

    # Create workout WITHOUT template
    workout_without_template = WorkoutDB(
        user_id=test_user.id,
        template_id=None,
        date=date(2025, 12, 10),
    )
    db_session.add(workout_without_template)
    db_session.commit()

    # Refresh to load relationships
    db_session.refresh(workout_with_template)
    db_session.refresh(workout_without_template)
    db_session.refresh(template)

    # Verify relationships
    assert workout_with_template.template_id == template.id
    assert workout_with_template.template == template
    assert workout_without_template.template_id is None
    assert workout_without_template.template is None

    # Verify backref - template.workouts should include the workout
    assert len(template.workouts) == 1
    assert template.workouts[0].id == workout_with_template.id


def test_get_workout_snapshots_template(client, db_session, test_user):
    """Test that getting a workout snapshots template exercises."""
    from models import TemplateDB, WorkoutDB

    # Create a template
    template = TemplateDB(
        user_id=test_user.id,
        name="Upper Body",
        description="Test template",
        exercises=[
            {"name": "Bench Press", "sets": 4, "rep_min": 6, "rep_max": 8},
            {"name": "Barbell Rows", "sets": 4, "rep_min": 8, "rep_max": 10},
        ],
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    # Create workout referencing template (no exercises)
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()

    # GET the workout - should trigger snapshot
    response = client.get(f"/api/v1/workouts/{workout.id}")
    assert response.status_code == 200
    data = response.json()

    # Verify exercises were snapshotted
    assert "exercises" in data
    assert data["exercises"] is not None
    assert len(data["exercises"]) == 2

    # Verify exercise structure
    first_exercise = data["exercises"][0]
    assert first_exercise["name"] == "Bench Press"
    assert first_exercise["target_sets"] == 4
    assert first_exercise["target_rep_min"] == 6
    assert first_exercise["target_rep_max"] == 8
    assert "sets" in first_exercise
    assert len(first_exercise["sets"]) == 4
    # Verify sets are empty (ready for logging)
    assert first_exercise["sets"][0]["reps"] is None
    assert first_exercise["sets"][0]["weight"] is None
    assert first_exercise["sets"][0]["completed"] is False


def test_update_workout_snapshots_on_start(client, db_session, test_user):
    """Test that setting start_time snapshots template exercises."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Leg Day",
        description="Lower body",
        exercises=[{"name": "Squat", "sets": 5, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout without exercises
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # PATCH with start_time - should trigger snapshot
    response = client.patch(
        f"/api/v1/workouts/{workout_id}",
        json={"start_time": "2025-12-20T09:00:00"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify exercises were snapshotted
    assert data["exercises"] is not None
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["name"] == "Squat"
    assert data["exercises"][0]["target_sets"] == 5


def test_update_workout_exercises(client, db_session, test_user):
    """Test updating workout exercises via PATCH /exercises endpoint."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Push Day",
        description="Chest and triceps",
        exercises=[{"name": "Bench Press", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Update exercises with performance data
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {"reps": 10, "weight": 135.0, "completed": True, "notes": None},
                        {"reps": 10, "weight": 135.0, "completed": True, "notes": None},
                        {"reps": 8, "weight": 135.0, "completed": True, "notes": None},
                    ],
                    "notes": "Felt strong",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Verify exercises were updated
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["sets"][0]["reps"] == 10
    assert data["exercises"][0]["sets"][0]["weight"] == 135.0
    assert data["exercises"][0]["sets"][0]["completed"] is True
    assert data["exercises"][0]["notes"] == "Felt strong"


def test_update_workout_exercises_already_finished(client, db_session, test_user):
    """Test that updating exercises on a finished workout fails."""
    from models import WorkoutDB

    # Create finished workout with exercises
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
        end_time=datetime(2025, 12, 20, 10, 30, 0),
        exercises=[
            {
                "name": "Squat",
                "target_sets": 5,
                "target_rep_min": 5,
                "target_rep_max": 5,
                "sets": [
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None}
                ],
                "notes": None,
            }
        ],
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to update exercises
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Squat",
                    "target_sets": 5,
                    "target_rep_min": 5,
                    "target_rep_max": 5,
                    "sets": [
                        {"reps": 6, "weight": 235.0, "completed": True, "notes": None}
                    ],
                    "notes": "Modified",
                }
            ]
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot modify a finished workout"


def test_workout_exercises_persisted(client, db_session, test_user):
    """Test that exercise data is persisted to database."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test",
        exercises=[{"name": "Squat", "sets": 1, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Update exercises
    client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Squat",
                    "target_sets": 1,
                    "target_rep_min": 5,
                    "target_rep_max": 5,
                    "sets": [
                        {"reps": 5, "weight": 225.0, "completed": True, "notes": None}
                    ],
                    "notes": None,
                }
            ]
        },
    )

    # Retrieve workout directly from DB
    db_workout = db_session.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    assert db_workout.exercises is not None
    assert db_workout.exercises[0]["sets"][0]["reps"] == 5
    assert db_workout.exercises[0]["sets"][0]["weight"] == 225.0


def test_workout_customization_independent_of_template(client, db_session, test_user):
    """Test that workout customization doesn't affect template."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Original",
        exercises=[{"name": "Exercise A", "sets": 3, "rep_min": 10, "rep_max": 12}],
    )
    db_session.add(template)
    db_session.commit()
    template_id = template.id

    # Create workout
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template_id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Modify workout exercises (add a different exercise)
    client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Exercise B",  # Different from template
                    "target_sets": 4,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(4)
                    ],
                    "notes": None,
                }
            ]
        },
    )

    # Verify workout has modified exercises
    response = client.get(f"/api/v1/workouts/{workout_id}")
    assert response.json()["exercises"][0]["name"] == "Exercise B"

    # Verify template is unchanged
    db_template = (
        db_session.query(TemplateDB).filter(TemplateDB.id == template_id).first()
    )
    assert db_template.exercises[0]["name"] == "Exercise A"


def test_list_workouts_excludes_exercises(client, db_session, test_user):
    """Test that list endpoint without date filter does not snapshot exercises."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test Template",
        exercises=[{"name": "Squat", "sets": 5, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout (exercises not yet snapshotted)
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()

    # List workouts without date filter - should NOT snapshot exercises
    response = client.get("/api/v1/workouts")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    workout_data = data[0]

    # Verify basic fields are present
    assert "id" in workout_data
    assert "template_id" in workout_data
    assert "date" in workout_data

    # Verify exercises field exists but is None (not snapshotted)
    assert "exercises" in workout_data
    assert workout_data["exercises"] is None


def test_list_workouts_with_date_filter_includes_exercises(
    client, db_session, test_user
):
    """Test that list endpoint with date filter snapshots and includes exercises."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test Template",
        exercises=[{"name": "Squat", "sets": 5, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout on specific date (exercises not yet snapshotted)
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()

    # List workouts WITH date filter - should snapshot and include exercises
    response = client.get("/api/v1/workouts?date=2025-12-20")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    workout_data = data[0]

    # Verify basic fields are present
    assert "id" in workout_data
    assert "template_id" in workout_data
    assert "date" in workout_data

    # Verify exercises ARE included (and were snapshotted)
    assert "exercises" in workout_data
    assert workout_data["exercises"] is not None
    assert len(workout_data["exercises"]) == 1
    assert workout_data["exercises"][0]["name"] == "Squat"
    assert workout_data["exercises"][0]["target_sets"] == 5


def test_get_workout_includes_exercises(client, db_session, test_user):
    """Test that get single workout endpoint includes exercise data."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test Template",
        exercises=[{"name": "Deadlift", "sets": 3, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Get single workout - should include exercises
    response = client.get(f"/api/v1/workouts/{workout_id}")
    assert response.status_code == 200
    data = response.json()

    # Verify basic fields are present
    assert "id" in data
    assert "template_id" in data
    assert "date" in data

    # Verify exercises ARE included (and snapshotted)
    assert "exercises" in data
    assert data["exercises"] is not None
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["name"] == "Deadlift"


# ========== Exercise Tracking Tests ==========


@pytest.fixture
def workout_with_exercises(db_session, test_user):
    """Create a workout with template and snapshotted exercises."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Push Day",
        exercises=[
            {"name": "Bench Press", "sets": 4, "rep_min": 6, "rep_max": 8},
            {"name": "Overhead Press", "sets": 3, "rep_min": 8, "rep_max": 10},
        ],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout with snapshotted exercises
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
        exercises=[
            {
                "name": "Bench Press",
                "target_sets": 4,
                "target_rep_min": 6,
                "target_rep_max": 8,
                "sets": [
                    {"reps": None, "weight": None, "completed": False, "notes": None}
                    for _ in range(4)
                ],
                "notes": None,
            },
            {
                "name": "Overhead Press",
                "target_sets": 3,
                "target_rep_min": 8,
                "target_rep_max": 10,
                "sets": [
                    {"reps": None, "weight": None, "completed": False, "notes": None}
                    for _ in range(3)
                ],
                "notes": None,
            },
        ],
    )
    db_session.add(workout)
    db_session.commit()
    db_session.refresh(workout)
    return workout


def test_add_sets_to_exercise(client, workout_with_exercises):
    """Test adding additional sets to an exercise during workout."""
    workout_id = workout_with_exercises.id

    # Add 2 extra sets to Bench Press (4 → 6 sets)
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 7, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 6, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": 8,
                            "weight": 175.0,
                            "completed": True,
                            "notes": "Extra set 1",
                        },
                        {
                            "reps": 8,
                            "weight": 175.0,
                            "completed": True,
                            "notes": "Extra set 2",
                        },
                    ],
                    "notes": "Added volume",
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 7, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 6, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 175.0, "completed": True, "notes": "Extra set 1"},
                {"reps": 8, "weight": 175.0, "completed": True, "notes": "Extra set 2"},
            ],
            "notes": "Added volume",
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after adding sets should match expected",
    )


def test_delete_sets_from_exercise(client, workout_with_exercises):
    """Test removing sets from an exercise."""
    workout_id = workout_with_exercises.id

    # Delete last 2 sets from Bench Press (4 → 2 sets)
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": 6,
                            "weight": 185.0,
                            "completed": True,
                            "notes": "Cut short",
                        },
                    ],
                    "notes": "Only did 2 sets",
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 6, "weight": 185.0, "completed": True, "notes": "Cut short"},
            ],
            "notes": "Only did 2 sets",
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after deleting sets should match expected",
    )


def test_delete_sets_preserves_other_exercises(client, workout_with_exercises):
    """
    Regression test: Verify that deleting sets from one exercise
    doesn't accidentally modify other exercises.

    This test explicitly validates the bug scenario where deleting sets
    from the first exercise might inadvertently affect the second exercise.
    """
    workout_id = workout_with_exercises.id

    # Delete all but one set from Bench Press, leave Overhead Press untouched
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                    ],
                    "notes": "Reduced to 1 set",
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify first exercise has only 1 set AND second exercise still has all 3 sets
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
            ],
            "notes": "Reduced to 1 set",
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Deleting sets from first exercise should not affect second exercise",
    )


def test_change_reps_on_set(client, workout_with_exercises):
    """Test changing reps for a specific set."""
    workout_id = workout_with_exercises.id

    # Change reps on 3rd set
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": 5,
                            "weight": 185.0,
                            "completed": True,
                            "notes": "Tough set",
                        },
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                    ],
                    "notes": None,
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 5, "weight": 185.0, "completed": True, "notes": "Tough set"},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after changing reps on set should match expected",
    )


def test_change_weight_on_set(client, workout_with_exercises):
    """Test changing weight for a specific set."""
    workout_id = workout_with_exercises.id

    # Change weight on 2nd set
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": 8,
                            "weight": 190.0,
                            "completed": True,
                            "notes": "Bumped up",
                        },
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                    ],
                    "notes": None,
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 190.0, "completed": True, "notes": "Bumped up"},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after changing weight on set should match expected",
    )


def test_mark_set_complete(client, workout_with_exercises):
    """Test marking a set as completed during workout."""
    workout_id = workout_with_exercises.id

    # Mark first set complete with performance data
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                    ],
                    "notes": None,
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after marking set complete should match expected",
    )


def test_mark_set_incomplete(client, db_session, test_user):
    """Test unmarking a set (completed=false)."""
    from models import TemplateDB, WorkoutDB

    # Create workout with some completed sets
    template = TemplateDB(
        user_id=test_user.id,
        name="Test",
        exercises=[{"name": "Squat", "sets": 3, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
        exercises=[
            {
                "name": "Squat",
                "target_sets": 3,
                "target_rep_min": 5,
                "target_rep_max": 5,
                "sets": [
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                ],
                "notes": None,
            }
        ],
    )
    db_session.add(workout)
    db_session.commit()

    # Unmark 2nd set as incomplete
    response = client.patch(
        f"/api/v1/workouts/{workout.id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Squat",
                    "target_sets": 3,
                    "target_rep_min": 5,
                    "target_rep_max": 5,
                    "sets": [
                        {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                        {
                            "reps": 5,
                            "weight": 225.0,
                            "completed": False,
                            "notes": "Redo",
                        },
                        {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    ],
                    "notes": None,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of exercise
    expected_exercises = [
        {
            "name": "Squat",
            "target_sets": 3,
            "target_rep_min": 5,
            "target_rep_max": 5,
            "sets": [
                {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                {"reps": 5, "weight": 225.0, "completed": False, "notes": "Redo"},
                {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
            ],
            "notes": None,
        }
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after marking set incomplete should match expected",
    )


def test_complete_tracking_flow(client, db_session, test_user):
    """Test realistic workout tracking: start, update sets progressively, finish."""
    from models import TemplateDB, WorkoutDB

    # Create template and workout
    template = TemplateDB(
        user_id=test_user.id,
        name="Upper",
        exercises=[{"name": "Bench Press", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.commit()

    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Start workout
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 200

    # Mark set 1 complete
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {"reps": 10, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                    ],
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 200

    # Mark set 2 complete with different reps
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {"reps": 10, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 9, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                    ],
                    "notes": None,
                }
            ]
        },
    )
    assert response.status_code == 200

    # Add extra set and mark complete
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {"reps": 10, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 9, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": 10,
                            "weight": 175.0,
                            "completed": True,
                            "notes": "Backoff set",
                        },
                    ],
                    "notes": "Felt strong",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Verify complete final state
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": 10, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 9, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {
                    "reps": 10,
                    "weight": 175.0,
                    "completed": True,
                    "notes": "Backoff set",
                },
            ],
            "notes": "Felt strong",
        }
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after complete tracking flow should match expected",
    )


def test_update_multiple_exercises(client, workout_with_exercises):
    """Test updating sets across multiple exercises in one request."""
    workout_id = workout_with_exercises.id

    # Update both exercises simultaneously
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                        {"reps": 7, "weight": 185.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                    ],
                    "notes": "2 sets done",
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {"reps": 10, "weight": 95.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        },
                    ],
                    "notes": "Started OHP",
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of both exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 7, "weight": 185.0, "completed": True, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": "2 sets done",
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": 10, "weight": 95.0, "completed": True, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": "Started OHP",
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after updating multiple exercises should match expected",
    )


def test_remove_exercise_from_workout(client, workout_with_exercises):
    """Test removing an entire exercise from a workout."""
    workout_id = workout_with_exercises.id

    # Remove Overhead Press, keep only Bench Press
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {"reps": 8, "weight": 185.0, "completed": True, "notes": None}
                        for _ in range(4)
                    ],
                    "notes": "Removed OHP",
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of remaining exercise
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
                {"reps": 8, "weight": 185.0, "completed": True, "notes": None},
            ],
            "notes": "Removed OHP",
        }
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after removing exercise should match expected",
    )


def test_add_custom_exercise(client, workout_with_exercises):
    """Test adding an exercise not in the template."""
    workout_id = workout_with_exercises.id

    # Add Dumbbell Flyes
    response = client.patch(
        f"/api/v1/workouts/{workout_id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(4)
                    ],
                    "notes": None,
                },
                {
                    "name": "Overhead Press",
                    "target_sets": 3,
                    "target_rep_min": 8,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                },
                {
                    "name": "Dumbbell Flyes",
                    "target_sets": 3,
                    "target_rep_min": 12,
                    "target_rep_max": 15,
                    "sets": [
                        {"reps": 15, "weight": 30.0, "completed": True, "notes": None},
                        {"reps": 14, "weight": 30.0, "completed": True, "notes": None},
                        {"reps": 12, "weight": 30.0, "completed": True, "notes": None},
                    ],
                    "notes": "Added accessory",
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of all 3 exercises
    expected_exercises = [
        {
            "name": "Bench Press",
            "target_sets": 4,
            "target_rep_min": 6,
            "target_rep_max": 8,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Overhead Press",
            "target_sets": 3,
            "target_rep_min": 8,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Dumbbell Flyes",
            "target_sets": 3,
            "target_rep_min": 12,
            "target_rep_max": 15,
            "sets": [
                {"reps": 15, "weight": 30.0, "completed": True, "notes": None},
                {"reps": 14, "weight": 30.0, "completed": True, "notes": None},
                {"reps": 12, "weight": 30.0, "completed": True, "notes": None},
            ],
            "notes": "Added accessory",
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after adding custom exercise should match expected",
    )


def test_clear_set_data(client, db_session, test_user):
    """Test setting reps/weight back to null."""
    from models import WorkoutDB

    # Create workout with completed sets
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date.today(),
        exercises=[
            {
                "name": "Squat",
                "target_sets": 3,
                "target_rep_min": 5,
                "target_rep_max": 5,
                "sets": [
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                ],
                "notes": None,
            }
        ],
    )
    db_session.add(workout)
    db_session.commit()

    # Clear data on 2nd set
    response = client.patch(
        f"/api/v1/workouts/{workout.id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Squat",
                    "target_sets": 3,
                    "target_rep_min": 5,
                    "target_rep_max": 5,
                    "sets": [
                        {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": "Reset",
                        },
                        {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                    ],
                    "notes": None,
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state of exercise
    expected_exercises = [
        {
            "name": "Squat",
            "target_sets": 3,
            "target_rep_min": 5,
            "target_rep_max": 5,
            "sets": [
                {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
                {"reps": None, "weight": None, "completed": False, "notes": "Reset"},
                {"reps": 5, "weight": 225.0, "completed": True, "notes": None},
            ],
            "notes": None,
        }
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after clearing set data should match expected",
    )


def test_reorder_exercises(client, db_session, test_user):
    """Test that exercise order is preserved."""
    from models import WorkoutDB

    # Create workout with 3 exercises in order [A, B, C]
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date.today(),
        exercises=[
            {
                "name": "Exercise A",
                "target_sets": 1,
                "target_rep_min": 10,
                "target_rep_max": 10,
                "sets": [
                    {"reps": None, "weight": None, "completed": False, "notes": None}
                ],
                "notes": None,
            },
            {
                "name": "Exercise B",
                "target_sets": 1,
                "target_rep_min": 10,
                "target_rep_max": 10,
                "sets": [
                    {"reps": None, "weight": None, "completed": False, "notes": None}
                ],
                "notes": None,
            },
            {
                "name": "Exercise C",
                "target_sets": 1,
                "target_rep_min": 10,
                "target_rep_max": 10,
                "sets": [
                    {"reps": None, "weight": None, "completed": False, "notes": None}
                ],
                "notes": None,
            },
        ],
    )
    db_session.add(workout)
    db_session.commit()

    # Reorder to [C, A, B]
    response = client.patch(
        f"/api/v1/workouts/{workout.id}/exercises",
        json={
            "exercises": [
                {
                    "name": "Exercise C",
                    "target_sets": 1,
                    "target_rep_min": 10,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                    ],
                    "notes": None,
                },
                {
                    "name": "Exercise A",
                    "target_sets": 1,
                    "target_rep_min": 10,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                    ],
                    "notes": None,
                },
                {
                    "name": "Exercise B",
                    "target_sets": 1,
                    "target_rep_min": 10,
                    "target_rep_max": 10,
                    "sets": [
                        {
                            "reps": None,
                            "weight": None,
                            "completed": False,
                            "notes": None,
                        }
                    ],
                    "notes": None,
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify complete state with new order
    expected_exercises = [
        {
            "name": "Exercise C",
            "target_sets": 1,
            "target_rep_min": 10,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Exercise A",
            "target_sets": 1,
            "target_rep_min": 10,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
        {
            "name": "Exercise B",
            "target_sets": 1,
            "target_rep_min": 10,
            "target_rep_max": 10,
            "sets": [
                {"reps": None, "weight": None, "completed": False, "notes": None},
            ],
            "notes": None,
        },
    ]

    assert_exercises_equal(
        data["exercises"],
        expected_exercises,
        "Exercise state after reordering should match expected",
    )


# ========== Start Workout Tests ==========


def test_start_workout(client, db_session, test_user):
    """Test starting a workout with a template."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test Template",
        exercises=[{"name": "Bench Press", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout for today (not started yet)
    today = date.today()
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=today,
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Start the workout
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 200
    data = response.json()

    # Verify start_time is set
    assert data["start_time"] is not None
    assert data["end_time"] is None

    # Verify exercises were snapshotted
    assert data["exercises"] is not None
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["name"] == "Bench Press"
    assert data["exercises"][0]["target_sets"] == 3


def test_start_workout_without_template(client, db_session, test_user):
    """Test starting a workout without a template."""
    from models import WorkoutDB

    # Create workout without template for today
    today = date.today()
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=None,
        date=today,
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Start the workout
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 200
    data = response.json()

    # Verify start_time is set
    assert data["start_time"] is not None
    assert data["end_time"] is None
    assert data["exercises"] is None


def test_start_workout_already_started(client, db_session, test_user):
    """Test that starting an already started workout fails."""
    from models import WorkoutDB

    # Create workout that's already started for today
    today = date.today()
    workout = WorkoutDB(
        user_id=test_user.id,
        date=today,
        start_time=datetime.now(),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to start it again
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 400
    assert response.json()["detail"] == "Workout has already been started"


def test_start_workout_not_found(client):
    """Test starting a non-existent workout."""
    fake_id = uuid4()
    response = client.post(f"/api/v1/workouts/{fake_id}/start")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


def test_start_workout_not_today(client, db_session, test_user):
    """Test that starting a workout not scheduled for today fails."""
    from datetime import timedelta

    from models import WorkoutDB

    # Create workout scheduled for tomorrow
    tomorrow = date.today() + timedelta(days=1)
    workout = WorkoutDB(
        user_id=test_user.id,
        date=tomorrow,
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to start it
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 400
    assert "Can only start workouts scheduled for today" in response.json()["detail"]
    assert str(tomorrow) in response.json()["detail"]


def test_start_workout_past_date(client, db_session, test_user):
    """Test that starting a workout from the past fails."""
    from datetime import timedelta

    from models import WorkoutDB

    # Create workout scheduled for yesterday
    yesterday = date.today() - timedelta(days=1)
    workout = WorkoutDB(
        user_id=test_user.id,
        date=yesterday,
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to start it
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 400
    assert "Can only start workouts scheduled for today" in response.json()["detail"]
    assert str(yesterday) in response.json()["detail"]


# ========== Cancel Workout Tests ==========


def test_cancel_workout(client, db_session, test_user):
    """Test canceling a workout in progress."""
    from models import WorkoutDB

    # Create workout in progress
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Cancel the workout
    response = client.post(f"/api/v1/workouts/{workout_id}/cancel")
    assert response.status_code == 200
    data = response.json()

    # Verify start_time is cleared
    assert data["start_time"] is None
    assert data["end_time"] is None


def test_cancel_workout_not_started(client, db_session, test_user):
    """Test that canceling a workout that hasn't started fails."""
    from models import WorkoutDB

    # Create workout that hasn't been started
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to cancel it
    response = client.post(f"/api/v1/workouts/{workout_id}/cancel")
    assert response.status_code == 400
    assert response.json()["detail"] == "Workout has not been started"


def test_cancel_workout_already_finished(client, db_session, test_user):
    """Test that canceling a finished workout fails."""
    from models import WorkoutDB

    # Create finished workout
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
        end_time=datetime(2025, 12, 20, 10, 30, 0),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to cancel it
    response = client.post(f"/api/v1/workouts/{workout_id}/cancel")
    assert response.status_code == 400
    assert response.json()["detail"] == "Workout has already been finished"


def test_cancel_workout_not_found(client):
    """Test canceling a non-existent workout."""
    fake_id = uuid4()
    response = client.post(f"/api/v1/workouts/{fake_id}/cancel")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


# ========== Finish Workout Tests ==========


def test_finish_workout(client, db_session, test_user):
    """Test finishing a workout in progress."""
    from models import WorkoutDB

    # Create workout in progress
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Finish the workout
    response = client.post(f"/api/v1/workouts/{workout_id}/finish")
    assert response.status_code == 200
    data = response.json()

    # Verify end_time is set
    assert data["start_time"] is not None
    assert data["end_time"] is not None


def test_finish_workout_not_started(client, db_session, test_user):
    """Test that finishing a workout that hasn't started fails."""
    from models import WorkoutDB

    # Create workout that hasn't been started
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to finish it
    response = client.post(f"/api/v1/workouts/{workout_id}/finish")
    assert response.status_code == 400
    assert response.json()["detail"] == "Workout has not been started"


def test_finish_workout_already_finished(client, db_session, test_user):
    """Test that finishing an already finished workout fails."""
    from models import WorkoutDB

    # Create finished workout
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 20),
        start_time=datetime(2025, 12, 20, 9, 0, 0),
        end_time=datetime(2025, 12, 20, 10, 30, 0),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Try to finish it again
    response = client.post(f"/api/v1/workouts/{workout_id}/finish")
    assert response.status_code == 400
    assert response.json()["detail"] == "Workout has already been finished"


def test_finish_workout_not_found(client):
    """Test finishing a non-existent workout."""
    fake_id = uuid4()
    response = client.post(f"/api/v1/workouts/{fake_id}/finish")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


# ========== Integration Test ==========


def test_workout_lifecycle(client, db_session, test_user):
    """Test complete workout lifecycle: create → start → finish."""
    from models import TemplateDB, WorkoutDB

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Full Body",
        exercises=[{"name": "Squat", "sets": 5, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout for today
    today = date.today()
    response = client.post(
        "/api/v1/workouts",
        json={
            "date": today.isoformat(),
        },
    )
    assert response.status_code == 201
    workout_id = response.json()["id"]

    # Link workout to template manually
    # (in real app, this happens during training plan generation)
    workout = db_session.query(WorkoutDB).filter(WorkoutDB.id == workout_id).first()
    workout.template_id = template.id
    db_session.commit()

    # Start workout
    response = client.post(f"/api/v1/workouts/{workout_id}/start")
    assert response.status_code == 200
    data = response.json()
    assert data["start_time"] is not None
    assert data["end_time"] is None
    assert data["exercises"] is not None

    # Finish workout
    response = client.post(f"/api/v1/workouts/{workout_id}/finish")
    assert response.status_code == 200
    data = response.json()
    assert data["start_time"] is not None
    assert data["end_time"] is not None

    # Verify final state
    response = client.get(f"/api/v1/workouts/{workout_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["start_time"] is not None
    assert data["end_time"] is not None
    assert data["exercises"] is not None


# ========== Workout Suggestions Tests ==========


def test_suggest_workout_success(client, db_session, test_user):
    """Test successful workout suggestions with history."""
    from datetime import timedelta
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Upper Body",
        exercises=[
            {"name": "Bench Press", "sets": 4, "rep_min": 6, "rep_max": 8},
            {"name": "Barbell Rows", "sets": 4, "rep_min": 8, "rep_max": 10},
        ],
    )
    db_session.add(template)
    db_session.commit()

    # Create historical workouts (4 weeks back)
    today = date.today()
    for i in range(4):
        workout_date = today - timedelta(days=7 * (i + 1))
        workout = WorkoutDB(
            user_id=test_user.id,
            date=workout_date,
            start_time=datetime.combine(workout_date, datetime.min.time()),
            end_time=datetime.combine(workout_date, datetime.min.time())
            + timedelta(hours=1),
            exercises=[
                {
                    "name": "Bench Press",
                    "target_sets": 4,
                    "target_rep_min": 6,
                    "target_rep_max": 8,
                    "sets": [
                        {
                            "reps": 8,
                            "weight": 175 + i * 5,
                            "completed": True,
                            "notes": None,
                        }
                        for _ in range(4)
                    ],
                    "notes": None,
                }
            ],
        )
        db_session.add(workout)
    db_session.commit()

    # Create today's workout (not yet started)
    today_workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=today,
    )
    db_session.add(today_workout)
    db_session.commit()
    workout_id = today_workout.id

    # Mock AI response
    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Bench Press",
                "sets": [
                    {"reps": 8, "weight": 195.0},
                    {"reps": 8, "weight": 195.0},
                    {"reps": 7, "weight": 195.0},
                    {"reps": 6, "weight": 195.0},
                ],
                "notes": "Strong progression trend, ready for weight increase",
            },
            {
                "name": "Barbell Rows",
                "sets": [
                    {"reps": 10, "weight": 135.0},
                    {"reps": 10, "weight": 135.0},
                    {"reps": 9, "weight": 135.0},
                    {"reps": 8, "weight": 135.0},
                ],
                "notes": "No previous history - start conservatively",
            },
        ],
        overall_notes="Focus on controlled tempo for hypertrophy",
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response):
        response = client.post(f"/api/v1/workouts/{workout_id}/suggest", json={})

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "exercises" in data
    assert "overall_notes" in data
    assert len(data["exercises"]) == 2

    # Verify Bench Press suggestions
    bench = data["exercises"][0]
    assert bench["name"] == "Bench Press"
    assert len(bench["sets"]) == 4
    assert bench["sets"][0]["weight"] == 195.0
    assert bench["sets"][0]["reps"] == 8

    # Verify workout was NOT modified
    db_session.refresh(today_workout)
    assert today_workout.exercises is not None  # Snapshotted but not modified
    assert today_workout.exercises[0]["sets"][0]["weight"] is None  # Still empty


def test_suggest_workout_no_history(client, db_session, test_user):
    """Test workout suggestions with no historical data."""
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="New Program",
        exercises=[{"name": "Deadlift", "sets": 3, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout (no history)
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Mock AI response for new exercise
    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Deadlift",
                "sets": [
                    {"reps": 5, "weight": 135.0},
                    {"reps": 5, "weight": 135.0},
                    {"reps": 5, "weight": 135.0},
                ],
                "notes": "First session - focus on form",
            }
        ],
        overall_notes="Establish baseline performance",
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response):
        response = client.post(f"/api/v1/workouts/{workout_id}/suggest", json={})

    assert response.status_code == 200
    data = response.json()
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["name"] == "Deadlift"


def test_suggest_workout_with_training_phase(client, db_session, test_user):
    """Test that training context is passed to AI."""
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test",
        exercises=[{"name": "Squat", "sets": 3, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
    )
    db_session.add(workout)
    db_session.commit()

    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Squat",
                "sets": [{"reps": 5, "weight": 100.0} for _ in range(3)],
                "notes": "Deload protocol",
            }
        ],
        overall_notes="Recovery week",
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response) as mock_ai:
        response = client.post(
            f"/api/v1/workouts/{workout.id}/suggest",
            json={
                "training_phase": "deload",
                "goal": "recovery",
                "notes": "Feeling fatigued",
            },
        )

    assert response.status_code == 200
    # Verify AI was called with context
    mock_ai.assert_called_once()
    call_args = mock_ai.call_args
    user_prompt = call_args.kwargs["messages"][0]["content"]
    assert "TRAINING PHASE: deload" in user_prompt
    assert "TRAINING GOAL: recovery" in user_prompt
    assert "ADDITIONAL NOTES: Feeling fatigued" in user_prompt


def test_suggest_workout_not_found(client):
    """Test 404 for non-existent workout."""
    fake_id = uuid4()
    response = client.post(f"/api/v1/workouts/{fake_id}/suggest", json={})
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


def test_suggest_workout_already_completed(client, db_session, test_user):
    """Test 400 for already completed workout."""
    from models import WorkoutDB

    # Create completed workout
    workout = WorkoutDB(
        user_id=test_user.id,
        date=date(2025, 12, 1),
        start_time=datetime(2025, 12, 1, 9, 0, 0),
        end_time=datetime(2025, 12, 1, 10, 30, 0),
    )
    db_session.add(workout)
    db_session.commit()

    response = client.post(f"/api/v1/workouts/{workout.id}/suggest", json={})
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Cannot generate suggestions for completed workouts"
    )


def test_suggest_workout_no_template(client, db_session, test_user):
    """Test 400 for workout without template."""
    from models import WorkoutDB

    # Create workout without template
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=None,
        date=date.today(),
    )
    db_session.add(workout)
    db_session.commit()

    response = client.post(f"/api/v1/workouts/{workout.id}/suggest", json={})
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Cannot generate suggestions for workouts without a template"
    )


def test_suggest_workout_snapshots_template(client, db_session, test_user):
    """Test that suggestions endpoint snapshots template if needed."""
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test",
        exercises=[{"name": "Squat", "sets": 3, "rep_min": 5, "rep_max": 5}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout without exercises
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
        exercises=None,  # Not yet snapshotted
    )
    db_session.add(workout)
    db_session.commit()
    workout_id = workout.id

    # Verify exercises are None before call
    assert workout.exercises is None

    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Squat",
                "sets": [{"reps": 5, "weight": 135.0} for _ in range(3)],
                "notes": None,
            }
        ],
        overall_notes=None,
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response):
        response = client.post(f"/api/v1/workouts/{workout_id}/suggest", json={})

    assert response.status_code == 200

    # Verify exercises were snapshotted
    db_session.refresh(workout)
    assert workout.exercises is not None
    assert len(workout.exercises) == 1
    assert workout.exercises[0]["name"] == "Squat"


def test_suggest_workout_does_not_modify(client, db_session, test_user):
    """Test that suggestions are read-only (don't modify workout)."""
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template
    template = TemplateDB(
        user_id=test_user.id,
        name="Test",
        exercises=[{"name": "Bench Press", "sets": 3, "rep_min": 8, "rep_max": 10}],
    )
    db_session.add(template)
    db_session.commit()

    # Create workout and snapshot exercises
    workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=date.today(),
    )
    db_session.add(workout)
    db_session.commit()

    # Manually snapshot to get initial state
    from workout import snapshot_template_exercises

    workout.exercises = snapshot_template_exercises(db_session, template.id)
    db_session.commit()
    workout_id = workout.id

    # Capture original state
    original_exercises = workout.exercises.copy()

    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Bench Press",
                "sets": [{"reps": 10, "weight": 185.0} for _ in range(3)],
                "notes": "Increase weight",
            }
        ],
        overall_notes="Push hard",
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response):
        response = client.post(f"/api/v1/workouts/{workout_id}/suggest", json={})

    assert response.status_code == 200

    # Verify workout exercises were NOT modified
    db_session.refresh(workout)
    assert workout.exercises == original_exercises
    # Sets should still be empty
    assert workout.exercises[0]["sets"][0]["weight"] is None
    assert workout.exercises[0]["sets"][0]["reps"] is None


def test_suggest_workout_partial_history(client, db_session, test_user):
    """Test suggestions with mixed exercise history."""
    from datetime import timedelta
    from unittest.mock import patch

    from models import TemplateDB, WorkoutDB
    from workouts_api import WorkoutSuggestionsResponse

    # Create template with 2 exercises
    template = TemplateDB(
        user_id=test_user.id,
        name="Mixed",
        exercises=[
            {"name": "Squat", "sets": 3, "rep_min": 5, "rep_max": 5},
            {"name": "Leg Press", "sets": 3, "rep_min": 10, "rep_max": 12},
        ],
    )
    db_session.add(template)
    db_session.commit()

    # Create history with only Squat (no Leg Press history)
    today = date.today()
    for i in range(3):
        workout_date = today - timedelta(days=7 * (i + 1))
        workout = WorkoutDB(
            user_id=test_user.id,
            date=workout_date,
            start_time=datetime.combine(workout_date, datetime.min.time()),
            end_time=datetime.combine(workout_date, datetime.min.time())
            + timedelta(hours=1),
            exercises=[
                {
                    "name": "Squat",
                    "target_sets": 3,
                    "target_rep_min": 5,
                    "target_rep_max": 5,
                    "sets": [
                        {
                            "reps": 5,
                            "weight": 225 + i * 10,
                            "completed": True,
                            "notes": None,
                        }
                        for _ in range(3)
                    ],
                    "notes": None,
                }
                # Note: No Leg Press in history
            ],
        )
        db_session.add(workout)
    db_session.commit()

    # Create today's workout
    today_workout = WorkoutDB(
        user_id=test_user.id,
        template_id=template.id,
        date=today,
    )
    db_session.add(today_workout)
    db_session.commit()

    mock_response = WorkoutSuggestionsResponse(
        exercises=[
            {
                "name": "Squat",
                "sets": [{"reps": 5, "weight": 245.0} for _ in range(3)],
                "notes": "Good progression trend",
            },
            {
                "name": "Leg Press",
                "sets": [{"reps": 12, "weight": 180.0} for _ in range(3)],
                "notes": "New exercise - establish baseline",
            },
        ],
        overall_notes="Mix of progression and baseline",
    )

    with patch("workouts_api.call_ai_agent", return_value=mock_response):
        response = client.post(f"/api/v1/workouts/{today_workout.id}/suggest", json={})

    assert response.status_code == 200
    data = response.json()

    # Verify both exercises have suggestions
    assert len(data["exercises"]) == 2
    assert data["exercises"][0]["name"] == "Squat"
    assert data["exercises"][1]["name"] == "Leg Press"
