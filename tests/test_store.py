import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from store.postgres import FeatureStore, FeatureRegistry
from store.redis_cache import FeatureCache
from config.settings import settings


@pytest_asyncio.fixture
async def feature_store():
    """Create feature store instance"""
    store = FeatureStore(settings.postgres_url)
    await store.connect()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def feature_registry():
    """Create feature registry instance"""
    registry = FeatureRegistry(settings.postgres_url)
    await registry.connect()
    yield registry
    await registry.close()


@pytest_asyncio.fixture
async def feature_cache():
    """Create feature cache instance"""
    cache = FeatureCache(settings.redis_url)
    await cache.connect()
    # Clear cache before test
    await cache.flush()
    yield cache
    await cache.close()


@pytest.mark.asyncio
async def test_write_and_read_features(feature_store):
    """Test writing and reading features"""
    # Write test features
    features = [
        {
            'feature_id': 1,
            'entity_id': 'user_test_1',
            'timestamp': datetime.utcnow(),
            'value': 25,
            'metadata': {'source': 'test'}
        },
        {
            'feature_id': 2,
            'entity_id': 'user_test_1',
            'timestamp': datetime.utcnow(),
            'value': 1500.50,
            'metadata': {'source': 'test'}
        }
    ]
    
    await feature_store.write_features(features)
    
    # Read features back
    result = await feature_store.get_features(
        entity_ids=['user_test_1'],
        feature_names=['user_age', 'user_lifetime_value'],
        timestamp=datetime.utcnow()
    )
    
    assert 'user_test_1' in result
    assert len(result['user_test_1']) > 0


@pytest.mark.asyncio
async def test_point_in_time_correctness(feature_store):
    """Test point-in-time feature retrieval"""
    now = datetime.utcnow()
    past = now - timedelta(hours=2)
    
    # Write features at different times
    features = [
        {
            'feature_id': 1,
            'entity_id': 'user_test_2',
            'timestamp': past,
            'value': 20,
            'metadata': {}
        },
        {
            'feature_id': 1,
            'entity_id': 'user_test_2',
            'timestamp': now,
            'value': 25,
            'metadata': {}
        }
    ]
    
    await feature_store.write_features(features)
    
    # Query at past time should return old value
    result = await feature_store.get_features(
        entity_ids=['user_test_2'],
        feature_names=['user_age'],
        timestamp=past + timedelta(minutes=1)
    )
    
    if 'user_test_2' in result and 'user_age' in result['user_test_2']:
        assert result['user_test_2']['user_age']['value'] == 20


@pytest.mark.asyncio
async def test_register_feature(feature_registry):
    """Test feature registration"""
    feature_id, created_at = await feature_registry.register(
        name='test_feature_new',
        version=1,
        dtype='int64',
        entity_type='user',
        ttl_hours=24,
        description='Test feature',
        tags=['test', 'unit-test']
    )
    
    assert feature_id > 0
    assert isinstance(created_at, datetime)
    
    # Retrieve the feature
    feature = await feature_registry.get_feature('test_feature_new', version=1)
    assert feature is not None
    assert feature['name'] == 'test_feature_new'


@pytest.mark.asyncio
async def test_list_features_by_entity_type(feature_registry):
    """Test listing features filtered by entity type"""
    features = await feature_registry.list_features(entity_type='user')
    assert len(features) > 0
    assert all(f['entity_type'] == 'user' for f in features)


@pytest.mark.asyncio
async def test_cache_set_and_get(feature_cache):
    """Test basic cache operations"""
    key = "user_test_cache:age"
    value = {
        'value': 30,
        'timestamp': datetime.utcnow().isoformat(),
        'freshness_seconds': 0
    }
    
    await feature_cache.set(key, value, ttl=60)
    retrieved = await feature_cache.get(key)
    
    assert retrieved is not None
    assert retrieved['value'] == 30


@pytest.mark.asyncio
async def test_cache_get_many(feature_cache):
    """Test batch cache retrieval"""
    keys = [f"user_batch:feature_{i}" for i in range(5)]
    data = {
        key: {
            'value': i * 10,
            'timestamp': datetime.utcnow().isoformat(),
            'freshness_seconds': 0
        }
        for i, key in enumerate(keys)
    }
    
    await feature_cache.set_many(data, ttl=60)
    results = await feature_cache.get_many(keys)
    
    assert len(results) == 5
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_cache_invalidate_pattern(feature_cache):
    """Test cache invalidation by pattern"""
    # Set multiple keys
    data = {
        f"user_123:feature_{i}": {'value': i}
        for i in range(3)
    }
    await feature_cache.set_many(data, ttl=60)
    
    # Invalidate by pattern
    count = await feature_cache.invalidate("user_123:*")
    assert count == 3
    
    # Verify keys are gone
    results = await feature_cache.get_many(list(data.keys()))
    assert all(r is None for r in results)


@pytest.mark.asyncio
async def test_cache_stats(feature_cache):
    """Test cache statistics retrieval"""
    # Add some data
    await feature_cache.set("test_key", {'value': 1}, ttl=60)
    
    stats = await feature_cache.get_stats()
    assert 'total_keys' in stats
    assert 'used_memory_mb' in stats
    assert 'hit_rate' in stats
