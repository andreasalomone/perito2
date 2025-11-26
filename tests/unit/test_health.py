import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Test that the /healthz endpoint returns 200 and is accessible without auth."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}

def test_health_endpoint_head(client):
    """Test that the /healthz endpoint supports HEAD requests."""
    response = client.head("/healthz")
    assert response.status_code == 200
