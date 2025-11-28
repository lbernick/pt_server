from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to PT Server"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_read_item():
    response = client.get("/items/42")
    assert response.status_code == 200
    assert response.json() == {"item_id": 42, "q": None}


def test_read_item_with_query():
    response = client.get("/items/42?q=test")
    assert response.status_code == 200
    assert response.json() == {"item_id": 42, "q": "test"}


def test_create_item():
    item_data = {
        "name": "Test Item",
        "description": "A test item",
        "price": 10.99,
        "tax": 1.10,
    }
    response = client.post("/items/", json=item_data)
    assert response.status_code == 200
    data = response.json()
    assert data["item"]["name"] == "Test Item"
    assert data["item"]["price"] == 10.99
    assert data["item_with_tax"] == 12.09


def test_create_item_without_optional_fields():
    item_data = {"name": "Simple Item", "price": 5.00}
    response = client.post("/items/", json=item_data)
    assert response.status_code == 200
    data = response.json()
    assert data["item"]["name"] == "Simple Item"
    assert data["item"]["description"] is None
    assert data["item_with_tax"] == 5.00
