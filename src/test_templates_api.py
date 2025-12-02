"""Tests for template API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth import get_or_create_user
from database import get_db
from main import app
from models import TemplateDB


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
def sample_template(db_session, test_user):
    """Create a sample template in the database."""
    template = TemplateDB(
        user_id=test_user.id,
        name="Upper Body Strength",
        description="Focus on compound pressing and pulling",
        exercises=["Bench Press", "Barbell Rows", "Overhead Press"],
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def multiple_templates(db_session, test_user):
    """Create multiple templates in the database."""
    templates = [
        TemplateDB(
            user_id=test_user.id,
            name="Upper Body",
            description="Upper body workout",
            exercises=["Bench Press", "Rows"],
        ),
        TemplateDB(
            user_id=test_user.id,
            name="Lower Body",
            description="Lower body workout",
            exercises=["Squat", "Deadlift"],
        ),
        TemplateDB(
            user_id=test_user.id,
            name="Full Body",
            description="Full body workout",
            exercises=["Squat", "Bench", "Rows"],
        ),
    ]
    for template in templates:
        db_session.add(template)
    db_session.commit()
    for template in templates:
        db_session.refresh(template)
    return templates


def test_get_template(client, sample_template):
    """Test getting a specific template by ID."""
    response = client.get(f"/api/v1/templates/{sample_template.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(sample_template.id)
    assert data["name"] == "Upper Body Strength"
    assert data["description"] == "Focus on compound pressing and pulling"
    assert data["exercises"] == ["Bench Press", "Barbell Rows", "Overhead Press"]


def test_get_template_not_found(client):
    """Test getting a non-existent template."""
    fake_id = uuid4()
    response = client.get(f"/api/v1/templates/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"


def test_list_templates_empty(client):
    """Test listing templates when database is empty."""
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    assert response.json() == []


def test_list_templates(client, multiple_templates):
    """Test listing all templates."""
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    template_names = {t["name"] for t in data}
    assert template_names == {"Upper Body", "Lower Body", "Full Body"}

    # Verify structure of first template
    first_template = data[0]
    assert "id" in first_template
    assert "name" in first_template
    assert "description" in first_template
    assert "exercises" in first_template
    assert isinstance(first_template["exercises"], list)


def test_list_templates_pagination(client, db_session, test_user):
    """Test template pagination."""
    # Create 5 templates
    for i in range(5):
        template = TemplateDB(
            user_id=test_user.id,
            name=f"Template {i}",
            description=f"Description {i}",
            exercises=[f"Exercise {i}"],
        )
        db_session.add(template)
    db_session.commit()

    # Test skip and limit
    response = client.get("/api/v1/templates?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_templates_with_skip(client, multiple_templates):
    """Test listing templates with skip parameter."""
    response = client.get("/api/v1/templates?skip=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Should skip first template


def test_list_templates_with_limit(client, multiple_templates):
    """Test listing templates with limit parameter."""
    response = client.get("/api/v1/templates?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Should return only 2 templates


def test_template_exercises_structure(client, sample_template):
    """Test that exercises are returned as an array of strings."""
    response = client.get(f"/api/v1/templates/{sample_template.id}")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["exercises"], list)
    assert all(isinstance(exercise, str) for exercise in data["exercises"])
    assert len(data["exercises"]) == 3


def test_template_with_no_description(client, db_session):
    """Test template with null description."""
    template = TemplateDB(
        name="Minimal Template", description=None, exercises=["Push-ups"]
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    response = client.get(f"/api/v1/templates/{template.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["description"] is None
    assert data["name"] == "Minimal Template"
