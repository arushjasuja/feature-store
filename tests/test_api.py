import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from api.main import app


@pytest_asyncio.fixture
async def client():
    """Create test client with proper lifespan handling"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_online_features_unauthorized(client):
    """Test online features without API key"""
    response = await client.post(
        "/api/v1/features/online",
        json={
            "entity_id": "user_123",
            "feature_names": ["age", "lifetime_value"]
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_online_features_success(client):
    """Test successful online feature retrieval"""
    response = await client.post(
        "/api/v1/features/online",
        json={
            "entity_id": "user_123",
            "feature_names": ["user_age", "user_lifetime_value"]
        },
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "entity_id" in data
    assert "features" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_batch_features_success(client):
    """Test batch feature retrieval"""
    response = await client.post(
        "/api/v1/features/batch",
        json={
            "entity_ids": ["user_123", "user_456"],
            "feature_names": ["user_age", "user_lifetime_value"]
        },
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_batch_features_too_many_entities(client):
    """Test batch request with too many entities"""
    entity_ids = [f"user_{i}" for i in range(1001)]
    response = await client.post(
        "/api/v1/features/batch",
        json={
            "entity_ids": entity_ids,
            "feature_names": ["user_age"]
        },
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_feature(client):
    """Test feature registration"""
    response = await client.post(
        "/api/v1/features/register",
        json={
            "name": "test_feature",
            "version": 1,
            "dtype": "float64",
            "entity_type": "user",
            "ttl_hours": 24,
            "description": "Test feature",
            "tags": ["test"]
        },
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert "feature_id" in data


@pytest.mark.asyncio
async def test_list_features(client):
    """Test listing all features"""
    response = await client.get(
        "/api/v1/features",
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_get_feature_metadata(client):
    """Test getting feature metadata"""
    response = await client.get(
        "/api/v1/features/user_age",
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "user_age"
    assert "version" in data
    assert "dtype" in data


@pytest.mark.asyncio
async def test_get_nonexistent_feature(client):
    """Test getting metadata for nonexistent feature"""
    response = await client.get(
        "/api/v1/features/nonexistent_feature",
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalidate_cache(client):
    """Test cache invalidation"""
    response = await client.delete(
        "/api/v1/cache/invalidate/user_123",
        headers={"X-API-Key": "tenant1_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "invalidated_count" in data
