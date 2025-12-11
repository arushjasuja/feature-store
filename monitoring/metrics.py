from prometheus_client import Counter, Histogram, Gauge, Info

# API metrics
api_requests = Counter(
    'feature_store_api_requests_total',
    'Total number of API requests',
    ['endpoint', 'status', 'tenant']
)

api_latency = Histogram(
    'feature_store_api_latency_seconds',
    'API request latency in seconds',
    ['endpoint'],
    buckets=[.001, .0025, .005, .01, .025, .05, .1, .25, .5, 1, 2.5]
)

# Cache metrics
cache_hit_rate = Counter(
    'feature_store_cache_hits_total',
    'Total number of cache hits',
    ['feature']
)

cache_miss_rate = Counter(
    'feature_store_cache_misses_total',
    'Total number of cache misses',
    ['feature']
)

cache_size = Gauge(
    'feature_store_cache_size_bytes',
    'Current cache size in bytes'
)

cache_keys_total = Gauge(
    'feature_store_cache_keys_total',
    'Total number of keys in cache'
)

# Feature metrics
feature_freshness = Gauge(
    'feature_store_feature_freshness_seconds',
    'Age of cached feature in seconds',
    ['feature']
)

feature_writes = Counter(
    'feature_store_feature_writes_total',
    'Total number of feature writes',
    ['feature']
)

feature_reads = Counter(
    'feature_store_feature_reads_total',
    'Total number of feature reads',
    ['feature', 'source']  # source: cache or database
)

# Database metrics
db_query_duration = Histogram(
    'feature_store_db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1]
)

db_connection_pool_size = Gauge(
    'feature_store_db_connection_pool_size',
    'Current database connection pool size'
)

db_connection_pool_available = Gauge(
    'feature_store_db_connection_pool_available',
    'Available connections in database pool'
)

# Streaming metrics
kafka_lag = Gauge(
    'feature_store_kafka_consumer_lag',
    'Kafka consumer lag',
    ['topic', 'partition']
)

kafka_messages_consumed = Counter(
    'feature_store_kafka_messages_consumed_total',
    'Total number of Kafka messages consumed',
    ['topic']
)

spark_batch_duration = Histogram(
    'feature_store_spark_batch_duration_seconds',
    'Spark batch processing duration',
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

spark_records_processed = Counter(
    'feature_store_spark_records_processed_total',
    'Total number of records processed by Spark'
)

# System metrics
system_info = Info(
    'feature_store_system',
    'System information'
)

# Feature store specific metrics
entities_served = Counter(
    'feature_store_entities_served_total',
    'Total number of unique entities served',
    ['entity_type']
)

batch_request_size = Histogram(
    'feature_store_batch_request_size',
    'Number of entities per batch request',
    buckets=[1, 10, 50, 100, 250, 500, 1000]
)

# Error metrics
errors_total = Counter(
    'feature_store_errors_total',
    'Total number of errors',
    ['error_type', 'component']
)


def initialize_system_info():
    """Set static system information and initialize metrics"""
    import platform
    system_info.info({
        'version': '1.0.0',
        'python_version': platform.python_version(),
        'platform': platform.platform()
    })
    
    # Initialize metrics with zero values so they appear in /metrics output
    # This ensures metrics endpoint returns data even before any requests
    api_requests.labels(endpoint="/health", status=200, tenant="system").inc(0)
    api_latency.labels(endpoint="/health").observe(0)
    cache_hit_rate.labels(feature="system").inc(0)
    cache_miss_rate.labels(feature="system").inc(0)
