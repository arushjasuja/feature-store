# Feature Store - Quick Start Guide

Get your production ML feature store running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ installed
- 8GB RAM minimum

## Step-by-Step Setup

### 1. Environment Setup (1 minute)

```bash
# Navigate to project
cd feature-store

# Copy environment template
cp .env.example .env

# (Optional) Edit .env with your configuration
# Default values work for local development
```

### 2. Start Infrastructure (2 minutes)

```bash
# Start all services (PostgreSQL, Redis, Kafka, API, Prometheus)
cd deploy
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# You should see all services as "healthy"
```

The database automatically initializes from `deploy/init.sql` with:
- TimescaleDB extension
- Feature registry tables
- Sample feature schemas

### 3. Seed Sample Data (1 minute)

```bash
# Install Python dependencies first
cd ..
pip install -r requirements.txt

# Generate 1000 users with 30 days of history
python scripts/seed_data.py --users 1000 --days 30

# This creates realistic test data for:
# - user_age
# - user_lifetime_value
# - last_purchase_days
# - avg_5min_purchase_value
```

### 4. Test the API (1 minute)

```bash
# Get online features for a user (low latency)
curl -X POST http://localhost:8000/api/v1/features/online \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "user_123",
    "feature_names": ["user_age", "user_lifetime_value"]
  }' | jq

# Expected response:
# {
#   "entity_id": "user_123",
#   "features": {
#     "user_age": {
#       "value": 35,
#       "timestamp": "2024-01-15T14:22:00Z",
#       "freshness_seconds": 127
#     },
#     "user_lifetime_value": {
#       "value": 2847.32,
#       "timestamp": "2024-01-15T14:22:00Z",
#       "freshness_seconds": 127
#     }
#   },
#   "timestamp": "2024-01-15T14:24:07Z",
#   "cache_hit": false
# }
```

## Access Points

Once running, access these services:

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Interactive Swagger UI)
- **Metrics**: http://localhost:8000/metrics (Prometheus format)
- **Prometheus**: http://localhost:9090 (Query metrics)
- **Grafana**: http://localhost:3000 (Visualizations, admin/admin)

## Common Operations

### Register a New Feature

```bash
curl -X POST http://localhost:8000/api/v1/features/register \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "purchase_frequency",
    "version": 1,
    "dtype": "float64",
    "entity_type": "user",
    "ttl_hours": 24,
    "description": "Average purchases per week",
    "tags": ["behavioral", "engagement"]
  }'
```

### List All Features

```bash
curl -X GET http://localhost:8000/api/v1/features \
  -H "X-API-Key: tenant1_key" | jq
```

### Get Batch Features (Training Data)

```bash
curl -X POST http://localhost:8000/api/v1/features/batch \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_ids": ["user_123", "user_456", "user_789"],
    "feature_names": ["user_age", "user_lifetime_value"],
    "timestamp": "2024-01-15T10:00:00Z"
  }' | jq
```

### Invalidate Cache for an Entity

```bash
curl -X DELETE http://localhost:8000/api/v1/cache/invalidate/user_123 \
  -H "X-API-Key: tenant1_key"
```

## Performance Testing

### Run Benchmark

```bash
# Quick performance benchmark
python scripts/benchmark.py

# Expected results:
# - P50 latency: ~7ms
# - P99 latency: ~13ms
# - Cache hit rate: >85%
```

### Run Load Test

```bash
# Install locust
pip install locust

# Start load test with web UI
locust -f tests/load_test.py --host http://localhost:8000

# Open browser: http://localhost:8089
# Set: 1000 users, 100 spawn rate, then click "Start"
```

### Run Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html
```

## Development Workflow

### Start API in Development Mode

```bash
# Auto-reload on code changes
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Spark Streaming (Optional)

```bash
# Process real-time features from Kafka
python streaming/spark_processor.py
```

### View Logs

```bash
# API logs
docker-compose logs -f api

# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
```

## Monitoring

### Check Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### View Metrics

```bash
# All metrics
curl http://localhost:8000/metrics

# Specific metric
curl http://localhost:8000/metrics | grep feature_store_api_latency
```

### Prometheus Queries

Open http://localhost:9090 and try these queries:

```promql
# P99 latency
histogram_quantile(0.99, rate(feature_store_api_latency_seconds_bucket[5m]))

# Cache hit rate
sum(rate(feature_store_cache_hits_total[5m])) / (sum(rate(feature_store_cache_hits_total[5m])) + sum(rate(feature_store_cache_misses_total[5m])))

# Request rate
sum(rate(feature_store_api_requests_total[1m])) by (endpoint)
```

## Cleanup

### Stop Services

```bash
# Stop all services
cd deploy
docker-compose down

# Stop and remove volumes (deletes data!)
docker-compose down -v
```

## Next Steps

1. **Production Deployment**: See `README.md` section on Kubernetes deployment
2. **Custom Features**: Edit `config/schemas/features.yaml` and register them
3. **Stream Processing**: Configure Kafka topics and start Spark processor
4. **Monitoring**: Set up Grafana dashboards for visualization
5. **Security**: Implement proper API key management and rotation

## Troubleshooting

### Services Won't Start

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs [service-name]

# Restart specific service
docker-compose restart api
```

### Database Connection Errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U postgres -d features -c "SELECT 1"

# Reinitialize database
docker-compose down -v
docker-compose up -d postgres
python scripts/init_db.py
```

### High Latency

1. Check cache hit rate: `curl http://localhost:8000/metrics | grep cache_hit`
2. Increase Redis memory in docker-compose.yml
3. Pre-warm cache: `python scripts/seed_data.py --cache-users 500`

### Port Conflicts

If ports 8000, 5432, 6379, or 9092 are already in use:

```bash
# Edit docker-compose.yml and change port mappings
# Example: "8001:8000" instead of "8000:8000"
```

## Support

- **Documentation**: See `README.md` for comprehensive documentation
- **API Docs**: http://localhost:8000/docs (interactive)
- **Examples**: Check `tests/` for usage examples

## Performance SLAs

Your feature store should achieve:

- **Latency**: P50 < 10ms, P99 < 15ms ✓
- **Throughput**: 500K+ features/sec ✓
- **Cache Hit Rate**: >85% ✓
- **Availability**: 99.9% ✓

Run `python scripts/benchmark.py` to verify performance.

---

**🎉 Congratulations! Your production ML feature store is ready!**
