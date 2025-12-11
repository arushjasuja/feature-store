#!/usr/bin/env python3
"""
Seed database with sample feature data for testing and development.
"""
import json
import asyncio
import asyncpg
import random
from datetime import datetime, timedelta
from config.settings import settings


async def seed_features(conn, num_users=1000, days_back=30):
    """
    Seed feature values for testing.
    
    Args:
        conn: Database connection
        num_users: Number of user entities to create
        days_back: How many days of historical data to generate
    """
    print(f"Generating feature data for {num_users} users over {days_back} days...")
    
    # Get feature IDs
    features = await conn.fetch("SELECT id, name FROM features ORDER BY id")
    feature_map = {f['name']: f['id'] for f in features}
    
    print(f"Found {len(features)} features: {list(feature_map.keys())}")
    
    # Generate data
    feature_values = []
    now = datetime.now()
    
    for user_id in range(1, num_users + 1):
        entity_id = f"user_{user_id}"
        
        # Generate historical data points
        for day in range(days_back):
            timestamp = now - timedelta(days=day, hours=random.randint(0, 23))
            
            # Generate realistic feature values
            if 'user_age' in feature_map:
                feature_values.append((
                    feature_map['user_age'],
                    entity_id,
                    timestamp,
                    str(random.randint(18, 75)),  # Age between 18-75
                    '{}'
                ))
            
            if 'user_lifetime_value' in feature_map:
                feature_values.append((
                    feature_map['user_lifetime_value'],
                    entity_id,
                    timestamp,
                    str(round(random.uniform(100, 10000), 2)),  # LTV $100-$10,000
                    '{}'
                ))
            
            if 'last_purchase_days' in feature_map:
                feature_values.append((
                    feature_map['last_purchase_days'],
                    entity_id,
                    timestamp,
                    str(random.randint(0, 365)),  # Days since purchase
                    '{}'
                ))
            
            if 'avg_5min_purchase_value' in feature_map:
                feature_values.append((
                    feature_map['avg_5min_purchase_value'],
                    entity_id,
                    timestamp,
                    str(round(random.uniform(0, 500), 2)),  # Purchase value
                    '{"window": "5min"}'
                ))
        
        if user_id % 100 == 0:
            print(f"  Generated data for {user_id}/{num_users} users...")
    
    print(f"Total feature values to insert: {len(feature_values)}")
    
    # Batch insert
    print("Inserting data...")
    await conn.executemany(
        """
        INSERT INTO feature_values (feature_id, entity_id, timestamp, value, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (feature_id, entity_id, timestamp) DO NOTHING
        """,
        feature_values
    )
    
    print("✓ Data insertion complete")


async def seed_cache(num_hot_users=100):
    """
    Pre-populate Redis cache with hot entities.
    
    Args:
        num_hot_users: Number of frequently accessed users to cache
    """
    print(f"\nPre-populating cache with {num_hot_users} hot users...")
    
    from store.redis_cache import FeatureCache
    cache = FeatureCache(settings.redis_url)
    await cache.connect()
    
    cache_data = {}
    now = datetime.now()
    
    for user_id in range(1, num_hot_users + 1):
        entity_id = f"user_{user_id}"
        
        # Cache common features
        cache_data[f"{entity_id}:user_age"] = {
            'value': random.randint(18, 75),
            'timestamp': now.isoformat(),
            'freshness_seconds': 0
        }
        
        cache_data[f"{entity_id}:user_lifetime_value"] = {
            'value': round(random.uniform(100, 10000), 2),
            'timestamp': now.isoformat(),
            'freshness_seconds': 0
        }
    
    await cache.set_many(cache_data, ttl=3600)
    await cache.close()
    
    print(f"✓ Cached {len(cache_data)} feature values")


async def verify_data(conn):
    """Verify seeded data"""
    print("\nVerifying seeded data...")
    
    # Count feature values
    total_values = await conn.fetchval("SELECT COUNT(*) FROM feature_values")
    print(f"✓ Total feature values: {total_values:,}")
    
    # Count unique entities
    unique_entities = await conn.fetchval(
        "SELECT COUNT(DISTINCT entity_id) FROM feature_values"
    )
    print(f"✓ Unique entities: {unique_entities:,}")
    
    # Show date range
    date_range = await conn.fetchrow("""
        SELECT 
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest
        FROM feature_values
    """)
    print(f"✓ Date range: {date_range['earliest']} to {date_range['latest']}")
    
    # Feature value counts per feature
    feature_counts = await conn.fetch("""
        SELECT f.name, COUNT(*) as count
        FROM feature_values fv
        JOIN features f ON f.id = fv.feature_id
        GROUP BY f.name
        ORDER BY count DESC
    """)
    
    print("\nFeature value counts:")
    for row in feature_counts:
        print(f"  - {row['name']}: {row['count']:,}")


async def main():
    """Main entry point"""
    print("="*60)
    print("Feature Store - Data Seeding")
    print("="*60)
    print()
    
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description='Seed feature store with sample data')
    parser.add_argument('--users', type=int, default=1000, help='Number of users (default: 1000)')
    parser.add_argument('--days', type=int, default=30, help='Days of history (default: 30)')
    parser.add_argument('--cache-users', type=int, default=100, help='Users to pre-cache (default: 100)')
    args = parser.parse_args()
    
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.postgres_url)
        print("✓ Connected to database")
        
        # Seed features
        await seed_features(conn, num_users=args.users, days_back=args.days)
        
        # Verify data
        await verify_data(conn)
        
        # Close connection
        await conn.close()
        
        # Seed cache
        await seed_cache(num_hot_users=args.cache_users)
        
        print("\n" + "="*60)
        print("✓ Data seeding complete!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
