import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    """Test user registration and subsequent login."""
    # 1. Register a new user
    register_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    response = await client.post("/api/auth/register", json=register_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user_id" in data

    # 2. Login with the registered user
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    login_resp_data = response.json()
    assert "access_token" in login_resp_data
    assert "refresh_token" in login_resp_data
    assert "user_id" in login_resp_data

    # 3. Refresh token
    refresh_data = {
        "refresh_token": login_resp_data["refresh_token"]
    }
    response = await client.post("/api/auth/refresh", json=refresh_data)
    assert response.status_code == 200
    refresh_resp_data = response.json()
    assert "access_token" in refresh_resp_data
    assert "refresh_token" in refresh_resp_data
    assert "user_id" in refresh_resp_data
