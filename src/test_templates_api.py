"""Tests for template API endpoints."""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from database import get_db
from main import app
from models import TemplateDB

client = TestClient(app)


@pytest.fixture
def sample_template(db_session):
    """Create a sample template in the database."""
    template = TemplateDB(
        name="Upper Body Strength",
        description="Focus on compound pressing and pulling",
        exercises=["Bench Press", "Barbell Rows", "Overhead Press"],
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def multiple_templates(db_session):
    """Create multiple templates in the database."""
    templates = [
        TemplateDB(
            name="Upper Body",
            description="Upper body workout",
            exercises=["Bench Press", "Rows"],
        ),
        TemplateDB(
            name="Lower Body",
            description="Lower body workout",
            exercises=["Squat", "Deadlift"],
        ),
        TemplateDB(
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


@pytest.fixture
def test_client_with_db(db_session):
    """Create test client with database dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield client
    app.dependency_overrides.clear()


def test_get_template(test_client_with_db, sample_template):
    """Test getting a specific template by ID."""
    response = test_client_with_db.get(f"/api/v1/templates/{sample_template.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(sample_template.id)
    assert data["name"] == "Upper Body Strength"
    assert data["description"] == "Focus on compound pressing and pulling"
    assert data["exercises"] == ["Bench Press", "Barbell Rows", "Overhead Press"]
    assert "created_at" in data
    assert "updated_at" in data


def test_get_template_not_found(test_client_with_db):
    """Test getting a non-existent template."""
    fake_id = uuid4()
    response = test_client_with_db.get(f"/api/v1/templates/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"


def test_list_templates_empty(test_client_with_db):
    """Test listing templates when database is empty."""
    response = test_client_with_db.get("/api/v1/templates")
    assert response.status_code == 200
    assert response.json() == []


def test_list_templates(test_client_with_db, multiple_templates):
    """Test listing all templates."""
    response = test_client_with_db.get("/api/v1/templates")
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
    assert "created_at" in first_template
    assert "updated_at" in first_template
    assert isinstance(first_template["exercises"], list)


def test_list_templates_pagination(test_client_with_db, db_session):
    """Test template pagination."""
    # Create 5 templates
    for i in range(5):
        template = TemplateDB(
            name=f"Template {i}",
            description=f"Description {i}",
            exercises=[f"Exercise {i}"],
        )
        db_session.add(template)
    db_session.commit()

    # Test skip and limit
    response = test_client_with_db.get("/api/v1/templates?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_templates_with_skip(test_client_with_db, multiple_templates):
    """Test listing templates with skip parameter."""
    response = test_client_with_db.get("/api/v1/templates?skip=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Should skip first template


def test_list_templates_with_limit(test_client_with_db, multiple_templates):
    """Test listing templates with limit parameter."""
    response = test_client_with_db.get("/api/v1/templates?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Should return only 2 templates


def test_template_exercises_structure(test_client_with_db, sample_template):
    """Test that exercises are returned as an array of strings."""
    response = test_client_with_db.get(f"/api/v1/templates/{sample_template.id}")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["exercises"], list)
    assert all(isinstance(exercise, str) for exercise in data["exercises"])
    assert len(data["exercises"]) == 3


def test_template_with_no_description(test_client_with_db, db_session):
    """Test template with null description."""
    template = TemplateDB(
        name="Minimal Template", description=None, exercises=["Push-ups"]
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    response = test_client_with_db.get(f"/api/v1/templates/{template.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["description"] is None
    assert data["name"] == "Minimal Template"
