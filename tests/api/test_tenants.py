import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_tenant_creation_and_config(client: AsyncClient):
    """Test tenant creation, listing, and config retrieval."""
    # 1. Register a new user to own the tenant
    register_data = {
        "email": "tenant_owner@example.com",
        "password": "testpassword123",
        "full_name": "Tenant Owner"
    }
    response = await client.post("/api/auth/register", json=register_data)
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Create a tenant
    tenant_data = {
        "name": "Test Tenant",
        "timezone": "UTC"
    }
    response = await client.post("/api/tenants", json=tenant_data, headers=headers)
    assert response.status_code == 201
    tenant = response.json()
    assert tenant["name"] == "Test Tenant"
    tenant_id = tenant["id"]

    # 3. List tenants
    response = await client.get("/api/tenants", headers=headers)
    assert response.status_code == 200
    tenants = response.json()
    assert isinstance(tenants, list)
    assert len(tenants) == 1
    assert tenants[0]["id"] == tenant_id

    # 4. Get tenant config
    response = await client.get(f"/api/tenants/{tenant_id}/config", headers=headers)
    assert response.status_code == 200
    config = response.json()
    assert config["persona_name"] == "Assistant" # Default persona name

    # 5. Update tenant config
    update_data = {
        "persona_name": "New Persona",
        "tone": "friendly"
    }
    response = await client.patch(f"/api/tenants/{tenant_id}/config", json=update_data, headers=headers)
    assert response.status_code == 200
    updated_config = response.json()
    assert updated_config["persona_name"] == "New Persona"
    assert updated_config["tone"] == "friendly"
