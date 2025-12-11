"""Tests for workout CRUD API endpoints."""

from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth import get_or_create_user
from database import get_db
from main import app
from models import WorkoutDB


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
    assert "created_at" in data
    assert "updated_at" in data


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


def test_update_workout(client, sample_workout):
    """Test updating a workout."""
    response = client.patch(
        f"/api/v1/workouts/{sample_workout.id}",
        json={
            "date": "2025-12-05",
            "start_time": "2025-12-05T14:00:00",
            "end_time": "2025-12-05T15:30:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_workout.id)
    assert data["date"] == "2025-12-05"
    assert data["start_time"] == "2025-12-05T14:00:00"
    assert data["end_time"] == "2025-12-05T15:30:00"


def test_update_workout_partial(client, sample_workout):
    """Test partially updating a workout."""
    response = client.patch(
        f"/api/v1/workouts/{sample_workout.id}",
        json={"date": "2025-12-10"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2025-12-10"
    # Original times should be preserved
    assert data["start_time"] == "2025-11-30T09:00:00"
    assert data["end_time"] == "2025-11-30T10:30:00"


def test_update_workout_not_found(client):
    """Test updating a non-existent workout."""
    fake_id = uuid4()
    response = client.patch(
        f"/api/v1/workouts/{fake_id}",
        json={"date": "2025-12-05"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Workout not found"


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
    assert "created_at" in workout_data
    assert "updated_at" in workout_data

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
