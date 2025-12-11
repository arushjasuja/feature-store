#!/usr/bin/env python3
"""
Database initialization script for Feature Store.
Runs the SQL schema initialization and verifies the setup.
"""

import asyncio
import asyncpg
import sys
from pathlib import Path
from config.settings import settings


async def init_database():
    """Initialize database schema"""
    print("Connecting to PostgreSQL...")
    
    try:
        conn = await asyncpg.connect(settings.postgres_url)
        print("✓ Connected successfully")
        
        # Read SQL schema file
        sql_file = Path(__file__).parent.parent / "deploy" / "init.sql"
        if not sql_file.exists():
            print(f"✗ SQL file not found: {sql_file}")
            sys.exit(1)
        
        print(f"Reading SQL from: {sql_file}")
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute schema creation
        print("Executing schema creation...")
        await conn.execute(sql_content)
        print("✓ Schema created successfully")
        
        # Verify tables
        print("\nVerifying tables...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f"✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Verify features
        feature_count = await conn.fetchval("SELECT COUNT(*) FROM features")
        print(f"\n✓ Found {feature_count} pre-registered features")
        
        # Verify TimescaleDB extension
        extensions = await conn.fetch("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname = 'timescaledb'
        """)
        
        if extensions:
            ext = extensions[0]
            print(f"✓ TimescaleDB {ext['extversion']} is enabled")
        else:
            print("⚠ TimescaleDB extension not found")
        
        await conn.close()
        print("\n✓ Database initialization complete!")
        return True
        
    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        return False


async def test_connection():
    """Test database connection and basic operations"""
    print("\nTesting database connection...")
    
    try:
        conn = await asyncpg.connect(settings.postgres_url)
        
        # Test query
        result = await conn.fetchval("SELECT NOW()")
        print(f"✓ Connection test passed (server time: {result})")
        
        # Test feature retrieval
        features = await conn.fetch("SELECT name, version FROM features LIMIT 5")
        print(f"✓ Can query features table ({len(features)} samples)")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False


async def main():
    """Main entry point"""
    print("="*60)
    print("Feature Store - Database Initialization")
    print("="*60)
    print(f"Database: {settings.postgres_url.split('@')[1]}")  # Hide credentials
    print()
    
    # Initialize database
    if not await init_database():
        sys.exit(1)
    
    # Test connection
    if not await test_connection():
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✓ All checks passed! Database is ready.")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
