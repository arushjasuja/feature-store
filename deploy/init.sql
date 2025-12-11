-- Enable TimescaleDB extension for time-series data
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Feature registry table
-- Stores feature metadata and schemas
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    dtype VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    ttl_hours INT DEFAULT 24,
    description TEXT,
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Indexes for efficient feature lookups
CREATE INDEX IF NOT EXISTS idx_features_name ON features(name);
CREATE INDEX IF NOT EXISTS idx_features_entity_type ON features(entity_type);
CREATE INDEX IF NOT EXISTS idx_features_name_version ON features(name, version);

-- Feature values table (time-series hypertable)
-- Stores actual feature values with timestamps
CREATE TABLE IF NOT EXISTS feature_values (
    feature_id INT NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    entity_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    value JSONB NOT NULL,
    metadata JSONB,
    PRIMARY KEY (feature_id, entity_id, timestamp)
);

-- Convert to TimescaleDB hypertable for efficient time-series queries
SELECT create_hypertable('feature_values', 'timestamp', 
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Indexes for efficient feature retrieval
CREATE INDEX IF NOT EXISTS idx_feature_values_entity 
    ON feature_values (entity_id, feature_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feature_values_timestamp 
    ON feature_values (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feature_values_feature_timestamp
    ON feature_values (feature_id, timestamp DESC);

-- Enable compression for older data (compress data older than 7 days)
ALTER TABLE feature_values SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'feature_id, entity_id'
);

SELECT add_compression_policy('feature_values', 
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Retention policy (drop data older than 90 days)
-- Adjust based on your retention requirements
SELECT add_retention_policy('feature_values', 
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- Staging table for Spark writes (optional)
-- Used to batch insert features before merging into main table
CREATE TABLE IF NOT EXISTS feature_values_staging (
    entity_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    avg_5min DOUBLE PRECISION,
    stddev_5min DOUBLE PRECISION,
    max_5min DOUBLE PRECISION,
    min_5min DOUBLE PRECISION,
    last_updated TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_entity_time 
    ON feature_values_staging(entity_id, window_end DESC);

-- Continuous aggregate for hourly feature statistics (optional)
-- Pre-computes hourly aggregations for faster queries
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_feature_stats
WITH (timescaledb.continuous) AS
SELECT
    feature_id,
    entity_id,
    time_bucket('1 hour', timestamp) AS hour,
    COUNT(*) as update_count,
    MAX(timestamp) as last_update
FROM feature_values
GROUP BY feature_id, entity_id, hour
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('hourly_feature_stats',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at on features table
CREATE TRIGGER update_features_updated_at 
    BEFORE UPDATE ON features
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample feature schemas for testing
INSERT INTO features (name, version, dtype, entity_type, ttl_hours, description, tags) VALUES
    ('user_age', 1, 'int64', 'user', 24, 'User age in years', ARRAY['demographic']),
    ('user_lifetime_value', 1, 'float64', 'user', 24, 'Predicted customer lifetime value', ARRAY['revenue', 'prediction']),
    ('last_purchase_days', 1, 'int64', 'user', 24, 'Days since last purchase', ARRAY['engagement']),
    ('avg_5min_purchase_value', 1, 'float64', 'user', 1, '5-minute average purchase value', ARRAY['realtime', 'revenue']),
    ('product_view_count', 1, 'int64', 'product', 24, 'Total product views', ARRAY['engagement'])
ON CONFLICT (name, version) DO NOTHING;

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO feature_store_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO feature_store_app;

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_features_tags ON features USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_feature_values_value ON feature_values USING GIN(value);

ANALYZE features;
ANALYZE feature_values;
