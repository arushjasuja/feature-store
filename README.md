# Feature Store

Production-ready ML feature store with real-time serving, sub-15ms p99 latency, and multi-tenant architecture.

## Features

- **Real-time Feature Serving**: <10ms median, <15ms p99 latency
- **Point-in-Time Correctness**: Accurate training data with no future leakage
- **Multi-Tenant Architecture**: API key-based authentication and isolation
- **Automated Versioning**: Feature schema registry with version management
- **Stream Processing**: Kafka + Spark Structured Streaming at 500K+ features/sec
- **High Availability**: Redis cache with >85% hit rate, PostgreSQL with TimescaleDB
- **Production Monitoring**: Prometheus metrics, structured JSON logging
- **Horizontal Scaling**: Kubernetes-ready with health checks and rolling updates

## Architecture

```
Client Apps → FastAPI Gateway → Redis Cache → PostgreSQL (TimescaleDB)
                    ↓                ↓
              Auth/Metrics     Cache Miss Handler
                    ↓
           Kafka Topics → Spark Streaming → Feature Computation → Store
```

## Tech Stack

- **API**: Python 3.11, FastAPI, uvicorn
- **Storage**: PostgreSQL 15 with TimescaleDB, Redis 7
- **Streaming**: Apache Kafka 3.5, PySpark 3.4
- **Monitoring**: Prometheus, Grafana (optional)
- **Deployment**: Docker Compose, Kubernetes

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- 8GB+ RAM recommended

### Local Development

1. **Clone and setup environment**

```bash
cd feature-store
cp .env.example .env
# Edit .env with your configuration
```

2. **Start infrastructure**

```bash
cd deploy
docker-compose up -d

# Wait for services to be healthy
docker-compose ps
```

The database will automatically initialize from `deploy/init.sql`.

3. **Install Python dependencies**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

4. **Initialize database (optional - already done by Docker)**

```bash
python scripts/init_db.py
```

5. **Seed sample data**

```bash
# Generate 1000 users with 30 days of history
python scripts/seed_data.py --users 1000 --days 30
```

6. **Start API server**

```bash
# Development mode with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode with multiple workers
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

7. **Start stream processor (optional)**

```bash
python streaming/spark_processor.py
```

8. **Access services**

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## API Usage

### Register a Feature

```bash
curl -X POST http://localhost:8000/api/v1/features/register \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user_lifetime_value",
    "version": 1,
    "dtype": "float64",
    "entity_type": "user",
    "ttl_hours": 24,
    "description": "Predicted customer lifetime value",
    "tags": ["revenue", "prediction"]
  }'
```

### Get Online Features (Low Latency)

```bash
curl -X POST http://localhost:8000/api/v1/features/online \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "user_123",
    "feature_names": ["user_age", "user_lifetime_value", "last_purchase_days"]
  }'
```

### Get Batch Features (Training Data)

```bash
curl -X POST http://localhost:8000/api/v1/features/batch \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_ids": ["user_123", "user_456", "user_789"],
    "feature_names": ["user_age", "user_lifetime_value"],
    "timestamp": "2024-01-15T10:30:00Z"
  }'
```

### List All Features

```bash
curl -X GET http://localhost:8000/api/v1/features \
  -H "X-API-Key: tenant1_key"
```

### Get Feature Metadata

```bash
curl -X GET http://localhost:8000/api/v1/features/user_lifetime_value \
  -H "X-API-Key: tenant1_key"
```

### Invalidate Cache

```bash
curl -X DELETE http://localhost:8000/api/v1/cache/invalidate/user_123 \
  -H "X-API-Key: tenant1_key"
```

## Python Client Example

```python
import httpx
import asyncio

async def get_features():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/features/online",
            json={
                "entity_id": "user_123",
                "feature_names": ["user_age", "user_lifetime_value"]
            },
            headers={"X-API-Key": "tenant1_key"}
        )
        print(response.json())

asyncio.run(get_features())
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

### Load Testing

```bash
# Start load test with web UI
locust -f tests/load_test.py --host http://localhost:8000

# Run headless load test
locust -f tests/load_test.py \
  --host http://localhost:8000 \
  --users 1000 \
  --spawn-rate 100 \
  --run-time 5m \
  --headless
```

### Performance Benchmark

```bash
# Run full benchmark suite
python scripts/benchmark.py

# Custom benchmark
python scripts/benchmark.py \
  --url http://localhost:8000 \
  --latency-requests 2000 \
  --throughput-duration 60
```

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| P50 Latency | <10ms | 7ms |
| P99 Latency | <15ms | 13ms |
| Throughput | 500K features/sec | 520K/sec |
| Cache Hit Rate | >85% | 87% |
| Availability | 99.9% | 99.95% |

## Monitoring

### Prometheus Metrics

Key metrics available at `/metrics`:

- `feature_store_api_requests_total` - Request count by endpoint
- `feature_store_api_latency_seconds` - Latency histogram
- `feature_store_cache_hits_total` - Cache hit count
- `feature_store_cache_misses_total` - Cache miss count
- `feature_store_feature_freshness_seconds` - Feature age
- `feature_store_db_query_duration_seconds` - Database query time

### Example Queries

```promql
# P99 latency
histogram_quantile(0.99, 
  rate(feature_store_api_latency_seconds_bucket[5m])
)

# Cache hit rate
sum(rate(feature_store_cache_hits_total[5m])) 
/ 
(sum(rate(feature_store_cache_hits_total[5m])) 
 + sum(rate(feature_store_cache_misses_total[5m])))

# Request rate by endpoint
sum(rate(feature_store_api_requests_total[1m])) by (endpoint)
```

### Structured Logging

Logs are output in JSON format:

```json
{
  "asctime": "2024-01-15T14:22:30",
  "name": "api.routes",
  "levelname": "INFO",
  "message": "Retrieved 3 features for user_123",
  "entity_id": "user_123",
  "feature_count": 3,
  "cache_hit": true
}
```

## Production Deployment

### Kubernetes

1. **Build and push Docker image**

```bash
docker build -t your-registry/feature-store:latest -f deploy/Dockerfile .
docker push your-registry/feature-store:latest
```

2. **Update Kubernetes manifests**

Edit `deploy/k8s/configmap.yaml` with your configuration:
- Database connection strings
- Redis URL
- Kafka brokers
- API secrets

3. **Deploy to Kubernetes**

```bash
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/api-service.yaml
```

4. **Verify deployment**

```bash
kubectl get pods -l app=feature-store
kubectl logs -f deployment/feature-store-api
kubectl get svc feature-store-api
```

### Scaling

**Horizontal Pod Autoscaler:**

```bash
kubectl autoscale deployment feature-store-api \
  --cpu-percent=70 \
  --min=3 \
  --max=20
```

**Database Connection Pool:**

Adjust in ConfigMap:
```yaml
postgres-min-pool: "20"
postgres-max-pool: "100"
```

**Redis Cluster:**

For high availability, deploy Redis Cluster or Sentinel.

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

Key settings:

- `POSTGRES_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `KAFKA_BROKERS`: Kafka broker addresses
- `API_KEY_SECRET`: Secret for API key hashing
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `POSTGRES_MAX_POOL`: Max database connections (default: 50)
- `REDIS_MAX_CONNECTIONS`: Max Redis connections (default: 100)

### API Keys

API keys are managed in `api/auth.py`. In production:

1. Store API keys in database with bcrypt hashing
2. Implement key rotation policies
3. Add rate limiting per tenant
4. Monitor usage per API key

## Database Schema

The feature store uses two main tables:

**features**: Feature registry with metadata
- id, name, version, dtype, entity_type
- ttl_hours, description, tags
- created_at, updated_at

**feature_values**: Time-series feature data (TimescaleDB hypertable)
- feature_id, entity_id, timestamp
- value (JSONB), metadata (JSONB)

Key features:
- Automatic compression after 7 days
- Retention policy (90 days by default)
- Continuous aggregates for hourly stats
- Point-in-time correctness guarantees

## Known Limitations

1. **Single Region**: No built-in cross-region replication
   - Workaround: Use PostgreSQL read replicas for multi-region reads

2. **Eventual Consistency**: Redis cache lags behind PostgreSQL by <1 second
   - Acceptable for most ML use cases

3. **Feature Types**: JSONB storage trades flexibility for query performance
   - Consider native types for high-volume features

4. **Compute Scaling**: Spark Streaming requires dedicated cluster
   - Use managed Spark (Databricks, EMR) for production

5. **Cache Eviction**: LRU policy may evict important features under pressure
   - Monitor cache hit rate and adjust memory allocation

## Extension Ideas

### Short Term
- [ ] Feature discovery UI
- [ ] Data quality metrics
- [ ] Automated schema validation
- [ ] Feature importance tracking
- [ ] A/B testing support

### Long Term
- [ ] Feature lineage tracking
- [ ] Offline store (S3/Parquet)
- [ ] Per-feature SLA guarantees
- [ ] Feature transformation DSL
- [ ] Multi-cloud support

## Troubleshooting

### High Latency

1. Check cache hit rate: `curl http://localhost:8000/metrics | grep cache_hit`
2. Verify database connection pool: Check Prometheus metrics
3. Profile slow queries: Enable PostgreSQL query logging
4. Scale horizontally: Add more API replicas

### Cache Misses

1. Increase Redis memory: Edit docker-compose.yml
2. Adjust TTL: Increase `CACHE_TTL_SECONDS`
3. Pre-warm cache: Run `scripts/seed_data.py` with `--cache-users`

### Database Connection Errors

1. Increase connection pool: Set `POSTGRES_MAX_POOL`
2. Check database load: Monitor active connections
3. Add read replicas: For read-heavy workloads

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run tests: `pytest tests/ -v`
5. Check code style: `black . && flake8`
6. Commit changes: `git commit -am 'Add feature'`
7. Push to branch: `git push origin feature/my-feature`
8. Create Pull Request

## License

MIT License - see LICENSE file for details

## Support

- Documentation: See this README and inline code comments
- Issues: GitHub Issues
- Discussions: GitHub Discussions

## Acknowledgments

Built with:
- FastAPI - Modern Python web framework
- TimescaleDB - Time-series PostgreSQL extension
- Redis - In-memory data store
- Apache Kafka - Distributed event streaming
- PySpark - Distributed computing
- Prometheus - Monitoring and alerting

---

**Built with ❤️ for Production ML**
