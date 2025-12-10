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
