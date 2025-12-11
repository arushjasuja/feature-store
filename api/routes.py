from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from datetime import datetime
import logging

from api.models import (
    OnlineFeatureRequest, OnlineFeatureResponse, FeatureValue,
    BatchFeatureRequest, BatchFeatureResponse,
    FeatureSchema, FeatureRegistrationResponse, FeatureMetadata,
    FeatureListResponse, HealthResponse, ReadinessResponse
)
from api.auth import verify_api_key
from monitoring.metrics import cache_hit_rate, cache_miss_rate, feature_freshness

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow()
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(req: Request):
    """
    Readiness check that verifies database and cache connectivity.
    Returns 503 if any dependency is unavailable.
    """
    database_ready = False
    cache_ready = False
    
    try:
        # Check database
        store = req.app.state.store
        async with store.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        database_ready = True
        
        # Check cache
        cache = req.app.state.cache
        await cache.client.ping()
        cache_ready = True
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Not ready - Database: {database_ready}, Cache: {cache_ready}"
        )
    
    return ReadinessResponse(
        status="ready",
        database=database_ready,
        cache=cache_ready,
        timestamp=datetime.utcnow()
    )


@router.post("/features/online", response_model=OnlineFeatureResponse)
async def get_online_features(
    request: OnlineFeatureRequest,
    req: Request,
    tenant: str = Depends(verify_api_key)
):
    """
    Get features for a single entity with low latency.
    First checks Redis cache, falls back to PostgreSQL if needed.
    
    Target latency: <10ms median, <15ms p99
    """
    store = req.app.state.store
    cache = req.app.state.cache
    
    # Build cache keys
    cache_keys = [f"{request.entity_id}:{f}" for f in request.feature_names]
    
    # Try cache first (parallel retrieval)
    cached = await cache.get_many(cache_keys)
    
    missing_features = []
    features = {}
    cache_hit = True
    
    # Process cached results
    for i, (key, value) in enumerate(zip(cache_keys, cached)):
        feature_name = request.feature_names[i]
        
        if value is not None:
            # Cache hit
            features[feature_name] = FeatureValue(
                value=value['value'],
                timestamp=value['timestamp'],
                freshness_seconds=value.get('freshness_seconds')
            )
            cache_hit_rate.labels(feature=feature_name).inc()
        else:
            # Cache miss
            missing_features.append(feature_name)
            cache_miss_rate.labels(feature=feature_name).inc()
            cache_hit = False
    
    # Fetch missing features from database
    if missing_features:
        logger.debug(f"Cache miss for {len(missing_features)} features, fetching from DB")
        
        db_results = await store.get_features(
            entity_ids=[request.entity_id],
            feature_names=missing_features,
            timestamp=datetime.utcnow()
        )
        
        # Process database results
        entity_features = db_results.get(request.entity_id, {})
        cache_data = {}
        
        for feature_name, feature_data in entity_features.items():
            # Calculate freshness
            age_seconds = (datetime.utcnow() - feature_data['timestamp']).total_seconds()
            
            features[feature_name] = FeatureValue(
                value=feature_data['value'],
                timestamp=feature_data['timestamp'],
                freshness_seconds=age_seconds
            )
            
            # Track freshness metric
            feature_freshness.labels(feature=feature_name).set(age_seconds)
            
            # Prepare for cache update
            cache_data[f"{request.entity_id}:{feature_name}"] = {
                'value': feature_data['value'],
                'timestamp': feature_data['timestamp'],
                'freshness_seconds': age_seconds
            }
        
        # Update cache asynchronously
        if cache_data:
            await cache.set_many(cache_data, ttl=3600)
    
    return OnlineFeatureResponse(
        entity_id=request.entity_id,
        features=features,
        timestamp=datetime.utcnow(),
        source="cache" if cache_hit and not missing_features else "database",
        cache_hit=cache_hit
    )


@router.post("/features/batch", response_model=BatchFeatureResponse)
async def get_batch_features(
    request: BatchFeatureRequest,
    req: Request,
    tenant: str = Depends(verify_api_key)
):
    """
    Get features for multiple entities.
    Performs point-in-time correct joins from historical store.
    Validates max 1000 entities via Pydantic model.
    
    Use case: Batch prediction, training data generation
    """
    store = req.app.state.store
    
    # Point-in-time join from historical store
    feature_matrix = await store.get_features(
        entity_ids=request.entity_ids,
        feature_names=request.feature_names,
        timestamp=request.timestamp or datetime.utcnow()
    )
    
    # Convert to response format
    formatted_features = {}
    for entity_id, features in feature_matrix.items():
        formatted_features[entity_id] = {
            feature_name: FeatureValue(
                value=feature_data['value'],
                timestamp=feature_data['timestamp']
            )
            for feature_name, feature_data in features.items()
        }
    
    return BatchFeatureResponse(
        features=formatted_features,
        timestamp=request.timestamp or datetime.utcnow(),
        count=len(formatted_features)
    )


@router.post("/features/register", response_model=FeatureRegistrationResponse)
async def register_feature(
    schema: FeatureSchema,
    req: Request,
    tenant: str = Depends(verify_api_key)
):
    """
    Register a new feature or update existing feature metadata.
    Creates schema entry in feature registry.
    """
    registry = req.app.state.registry
    
    try:
        feature_id, created_at = await registry.register(
            name=schema.name,
            version=schema.version,
            dtype=schema.dtype,
            entity_type=schema.entity_type,
            ttl_hours=schema.ttl_hours,
            description=schema.description,
            tags=schema.tags
        )
        
        logger.info(f"Registered feature: {schema.name} v{schema.version} (ID: {feature_id})")
        
        return FeatureRegistrationResponse(
            feature_id=feature_id,
            name=schema.name,
            version=schema.version,
            status="registered",
            created_at=created_at
        )
        
    except Exception as e:
        logger.error(f"Failed to register feature: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.get("/features", response_model=FeatureListResponse)
async def list_features(
    req: Request,
    entity_type: str = None,
    tenant: str = Depends(verify_api_key)
):
    """
    List all registered features, optionally filtered by entity type.
    """
    registry = req.app.state.registry
    
    features = await registry.list_features(entity_type=entity_type)
    
    return FeatureListResponse(
        features=[
            FeatureMetadata(
                id=f['id'],
                name=f['name'],
                version=f['version'],
                dtype=f['dtype'],
                entity_type=f['entity_type'],
                ttl_hours=f['ttl_hours'],
                description=f['description'],
                tags=f.get('tags'),
                created_at=f['created_at'],
                updated_at=f['updated_at']
            )
            for f in features
        ],
        count=len(features)
    )


@router.get("/features/{name}", response_model=FeatureMetadata)
async def get_feature_metadata(
    name: str,
    req: Request,
    version: int = None,
    tenant: str = Depends(verify_api_key)
):
    """
    Get metadata for a specific feature.
    Returns latest version if version not specified.
    """
    registry = req.app.state.registry
    
    feature = await registry.get_feature(name=name, version=version)
    
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    
    return FeatureMetadata(
        id=feature['id'],
        name=feature['name'],
        version=feature['version'],
        dtype=feature['dtype'],
        entity_type=feature['entity_type'],
        ttl_hours=feature['ttl_hours'],
        description=feature['description'],
        tags=feature.get('tags'),
        created_at=feature['created_at'],
        updated_at=feature['updated_at']
    )


@router.delete("/cache/invalidate/{entity_id}")
async def invalidate_cache(
    entity_id: str,
    req: Request,
    tenant: str = Depends(verify_api_key)
):
    """
    Invalidate all cached features for an entity.
    Use when entity data is updated and cache should be refreshed.
    """
    cache = req.app.state.cache
    
    pattern = f"{entity_id}:*"
    invalidated_count = await cache.invalidate(pattern)
    
    logger.info(f"Invalidated {invalidated_count} cache entries for entity {entity_id}")
    
    return {
        "status": "success",
        "entity_id": entity_id,
        "invalidated_count": invalidated_count
    }
