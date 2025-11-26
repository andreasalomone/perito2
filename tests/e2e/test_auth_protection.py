import pytest

def test_unauthorized_access(app):
    """Verify protected routes require authentication."""
    # Create a fresh client without auth headers
    client = app.test_client()
    
    # List of protected routes to check (method, route)
    protected_routes = [
        ('GET', '/'),
        ('POST', '/upload'),
        ('GET', '/admin'),
        ('GET', '/admin/reports'),
        ('GET', '/admin/ai-control')
    ]
    
    for method, route in protected_routes:
        if method == 'GET':
            response = client.get(route)
        else:
            response = client.post(route)
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") is not None

def test_logout(client):
    """Verify logout clears session/auth."""
    # First verify we are logged in (client fixture has auth)
    response = client.get('/admin')
    assert response.status_code == 200
    
    # Logout
    response = client.get('/admin/logout')
    assert response.status_code == 401 # Logout returns 401 to trigger browser clear
    assert b"You have been logged out" in response.data
