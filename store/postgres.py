import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FeatureStore:
    """
    PostgreSQL-based feature store with TimescaleDB for time-series data.
    Provides point-in-time correct feature retrieval for training and serving.
    """
    
    def __init__(self, connection_string: str, min_pool: int = 10, max_pool: int = 50):
        self.pool = None
        self.conn_string = connection_string
        self.min_pool = min_pool
        self.max_pool = max_pool
    
    async def connect(self):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.conn_string,
                min_size=self.min_pool,
                max_size=self.max_pool,
                command_timeout=5,
                server_settings={
                    'application_name': 'feature_store'
                }
            )
            logger.info(f"PostgreSQL connection pool created (min={self.min_pool}, max={self.max_pool})")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")
    
    async def get_features(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Dict[str, Dict]]:
        """
        Get features for multiple entities with point-in-time correctness.
        
        Returns the latest feature values before the specified timestamp.
        This ensures training data doesn't include future information (time travel).
        
        Args:
            entity_ids: List of entity identifiers
            feature_names: List of feature names to retrieve
            timestamp: Point-in-time timestamp (defaults to now)
            
        Returns:
            Nested dict: {entity_id: {feature_name: {value, timestamp}}}
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Point-in-time correctness: get latest value before timestamp
        # DISTINCT ON ensures we get only one row per (entity_id, feature_name)
        query = """
            SELECT DISTINCT ON (fv.entity_id, f.name)
                fv.entity_id,
                f.name as feature_name,
                fv.value,
                fv.timestamp,
                fv.metadata
            FROM feature_values fv
            JOIN features f ON f.id = fv.feature_id
            WHERE fv.entity_id = ANY($1::text[])
                AND f.name = ANY($2::text[])
                AND fv.timestamp <= $3
            ORDER BY fv.entity_id, f.name, fv.timestamp DESC
        """
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, entity_ids, feature_names, timestamp)
            
            # Reshape to nested dict for easy access
            result = {}
            for row in rows:
                entity_id = row['entity_id']
                feature_name = row['feature_name']
                
                if entity_id not in result:
                    result[entity_id] = {}
                
                result[entity_id][feature_name] = {
                    'value': row['value'],  # asyncpg returns Python object from JSONB
                    'timestamp': row['timestamp'],
                    'metadata': row['metadata'] or {}  # asyncpg returns Python object from JSONB
                }
            
            logger.debug(f"Retrieved {len(rows)} feature values for {len(entity_ids)} entities")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get features: {e}")
            raise
    
    async def write_features(self, features: List[Dict]):
        """
        Batch write features to storage.
        Uses INSERT ON CONFLICT to handle duplicate timestamps.
        
        Args:
            features: List of feature dicts with keys:
                - feature_id: int
                - entity_id: str
                - timestamp: datetime
                - value: any JSON-serializable value
                - metadata: dict (optional)
        """
        if not features:
            return
        
        query = """
            INSERT INTO feature_values (feature_id, entity_id, timestamp, value, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (feature_id, entity_id, timestamp) 
            DO UPDATE SET 
                value = EXCLUDED.value,
                metadata = EXCLUDED.metadata
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    query,
                    [
                        (
                            f['feature_id'],
                            f['entity_id'],
                            f['timestamp'],
                            f['value'],  # asyncpg handles JSONB conversion
                            f.get('metadata', {})  # asyncpg handles JSONB conversion
                        )
                        for f in features
                    ]
                )
            
            logger.info(f"Wrote {len(features)} feature values to storage")
            
        except Exception as e:
            logger.error(f"Failed to write features: {e}")
            raise
    
    async def get_feature_history(
        self,
        entity_id: str,
        feature_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get feature value history for an entity within a time range.
        Useful for debugging and feature analysis.
        
        Args:
            entity_id: Entity identifier
            feature_name: Feature name
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of {value, timestamp, metadata} dicts ordered by timestamp
        """
        query = """
            SELECT fv.value, fv.timestamp, fv.metadata
            FROM feature_values fv
            JOIN features f ON f.id = fv.feature_id
            WHERE fv.entity_id = $1
                AND f.name = $2
                AND fv.timestamp >= $3
                AND fv.timestamp <= $4
            ORDER BY fv.timestamp ASC
        """
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, entity_id, feature_name, start_time, end_time)
            
            return [
                {
                    'value': row['value'],  # asyncpg returns Python object from JSONB
                    'timestamp': row['timestamp'],
                    'metadata': row['metadata'] or {}  # asyncpg returns Python object from JSONB
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get feature history: {e}")
            raise


class FeatureRegistry:
    """
    Feature registry for managing feature metadata and schemas.
    Tracks feature definitions, versions, and data types.
    """
    
    def __init__(self, connection_string: str):
        self.pool = None
        self.conn_string = connection_string
    
    async def connect(self):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.conn_string,
                min_size=5,
                max_size=20,
                command_timeout=5
            )
            logger.info("Feature registry connection pool created")
        except Exception as e:
            logger.error(f"Failed to create registry connection pool: {e}")
            raise
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Feature registry connection pool closed")
    
    async def register(
        self,
        name: str,
        version: int,
        dtype: str,
        entity_type: str,
        ttl_hours: int,
        description: str,
        tags: Optional[List[str]] = None
    ) -> tuple[int, datetime]:
        """
        Register a new feature or update existing feature metadata.
        
        Args:
            name: Feature name
            version: Feature version
            dtype: Data type (float64, int64, string, bool)
            entity_type: Entity type (user, product, session)
            ttl_hours: Time-to-live in hours
            description: Human-readable description
            tags: Optional list of tags
            
        Returns:
            Tuple of (feature_id, created_at)
        """
        query = """
            INSERT INTO features (name, version, dtype, entity_type, ttl_hours, description, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (name, version) 
            DO UPDATE SET
                dtype = EXCLUDED.dtype,
                entity_type = EXCLUDED.entity_type,
                ttl_hours = EXCLUDED.ttl_hours,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                updated_at = NOW()
            RETURNING id, created_at
        """
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, name, version, dtype, entity_type, ttl_hours, description, tags or []
                )
            
            logger.info(f"Registered feature: {name} v{version} (ID: {row['id']})")
            return row['id'], row['created_at']
            
        except Exception as e:
            logger.error(f"Failed to register feature: {e}")
            raise
    
    async def get_feature(self, name: str, version: Optional[int] = None) -> Optional[Dict]:
        """
        Get feature metadata by name and optional version.
        Returns latest version if version not specified.
        
        Args:
            name: Feature name
            version: Feature version (optional)
            
        Returns:
            Feature metadata dict or None if not found
        """
        if version:
            query = "SELECT * FROM features WHERE name = $1 AND version = $2"
            params = [name, version]
        else:
            query = "SELECT * FROM features WHERE name = $1 ORDER BY version DESC LIMIT 1"
            params = [name]
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get feature: {e}")
            raise
    
    async def list_features(self, entity_type: Optional[str] = None) -> List[Dict]:
        """
        List all registered features, optionally filtered by entity type.
        
        Args:
            entity_type: Optional entity type filter
            
        Returns:
            List of feature metadata dicts
        """
        if entity_type:
            query = "SELECT * FROM features WHERE entity_type = $1 ORDER BY name, version"
            params = [entity_type]
        else:
            query = "SELECT * FROM features ORDER BY name, version"
            params = []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to list features: {e}")
            raise
    
    async def get_feature_by_id(self, feature_id: int) -> Optional[Dict]:
        """Get feature metadata by ID"""
        query = "SELECT * FROM features WHERE id = $1"
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, feature_id)
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get feature by ID: {e}")
            raise
