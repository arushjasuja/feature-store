import redis.asyncio as redis
import msgpack
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureCache:
    """
    Redis-based feature cache for low-latency serving.
    Uses msgpack for efficient serialization and pipeline for batch operations.
    """
    
    def __init__(self, redis_url: str, max_connections: int = 100):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.client = None
    
    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We handle encoding with msgpack
                max_connections=self.max_connections,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            await self.client.ping()
            logger.info(f"Redis connection established (max_connections={self.max_connections})")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Dict]:
        """
        Get a single feature value from cache.
        
        Args:
            key: Cache key (format: "entity_id:feature_name")
            
        Returns:
            Feature value dict or None if not found
        """
        try:
            value = await self.client.get(key)
            if value:
                return msgpack.unpackb(value, raw=False)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    async def get_many(self, keys: List[str]) -> List[Optional[Dict]]:
        """
        Get multiple feature values in a single round-trip using pipeline.
        
        Args:
            keys: List of cache keys
            
        Returns:
            List of feature value dicts (None for cache misses)
        """
        if not keys:
            return []
        
        try:
            # Use pipeline for efficient batch retrieval
            pipe = self.client.pipeline()
            for key in keys:
                pipe.get(key)
            
            results = await pipe.execute()
            
            # Deserialize results
            return [
                msgpack.unpackb(r, raw=False) if r else None
                for r in results
            ]
            
        except Exception as e:
            logger.warning(f"Cache get_many failed: {e}")
            # Return all None on error to trigger database fallback
            return [None] * len(keys)
    
    async def set(self, key: str, value: Dict, ttl: int = 3600):
        """
        Set a single feature value in cache with TTL.
        
        Args:
            key: Cache key
            value: Feature value dict
            ttl: Time-to-live in seconds
        """
        try:
            serialized = msgpack.packb(value, use_bin_type=True)
            await self.client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
    
    async def set_many(self, data: Dict[str, Dict], ttl: int = 3600):
        """
        Set multiple feature values in a single round-trip using pipeline.
        
        Args:
            data: Dict of {key: value}
            ttl: Time-to-live in seconds
        """
        if not data:
            return
        
        try:
            # Use pipeline for efficient batch writes
            pipe = self.client.pipeline()
            for key, value in data.items():
                serialized = msgpack.packb(value, use_bin_type=True)
                pipe.setex(key, ttl, serialized)
            
            await pipe.execute()
            logger.debug(f"Cached {len(data)} feature values")
            
        except Exception as e:
            logger.warning(f"Cache set_many failed: {e}")
    
    async def invalidate(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "user_123:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern, count=100):
                keys.append(key)
            
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries for pattern: {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Cache invalidation failed for pattern {pattern}: {e}")
            return 0
    
    async def get_stats(self) -> Dict:
        """
        Get Redis cache statistics.
        
        Returns:
            Dict with cache stats (memory, keys, hit rate)
        """
        try:
            info = await self.client.info("stats")
            memory_info = await self.client.info("memory")
            keyspace = await self.client.info("keyspace")
            
            total_keys = 0
            if 'db0' in keyspace:
                total_keys = keyspace['db0']['keys']
            
            return {
                'total_keys': total_keys,
                'used_memory_mb': memory_info.get('used_memory', 0) / (1024 * 1024),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100
    
    async def flush(self):
        """
        Flush all keys in the current database.
        WARNING: Use with caution in production!
        """
        try:
            await self.client.flushdb()
            logger.warning("Redis cache flushed")
        except Exception as e:
            logger.error(f"Failed to flush cache: {e}")
            raise
