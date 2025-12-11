# Feature Store - Final Structure

## Directory Structure

```
feature-store/
├── api/                          # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # App initialization, lifespan, middleware
│   ├── routes.py                 # API endpoints
│   ├── models.py                 # Pydantic schemas
│   └── auth.py                   # API key authentication
│
├── store/                        # Storage layer
│   ├── __init__.py
│   ├── postgres.py               # PostgreSQL + TimescaleDB client
│   └── redis_cache.py            # Redis cache with msgpack
│
├── streaming/                    # Stream processing
│   ├── __init__.py
│   └── spark_processor.py        # Spark Structured Streaming
│
├── monitoring/                   # Observability
│   ├── __init__.py
│   ├── metrics.py                # Prometheus metrics
│   └── logger.py                 # Structured logging
│
├── config/                       # Configuration
│   ├── __init__.py
│   ├── settings.py               # Application settings
│   └── schemas/
│       └── features.yaml         # Sample feature definitions
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_api.py              # API tests
│   ├── test_store.py            # Storage tests
│   └── load_test.py             # Locust load tests
│
├── scripts/                      # Utility scripts
│   ├── init_db.py               # Database initialization
│   ├── seed_data.py             # Sample data generation
│   └── benchmark.py             # Performance benchmarking
│
├── deploy/                       # Deployment configs
│   ├── Dockerfile
│   ├── docker-compose.yml       # Local development stack
│   ├── init.sql                 # Database schema
│   ├── prometheus.yml
│   └── k8s/
│       ├── api-deployment.yaml
│       ├── api-service.yaml
│       └── configmap.yaml
│
├── .env.example                  # Environment template
├── .gitignore
├── LICENSE
├── Makefile                      # Common tasks
├── pytest.ini
├── requirements.txt
├── setup.py
├── start.sh                      # Quick start script
├── README.md                     # Main documentation
├── QUICKSTART.md                 # 5-minute guide
├── ARCHITECTURE.md               # System design
└── TROUBLESHOOTING.md            # Common issues

Total: 42 files (3,065 lines Python code)
```

## Quick Start

### Windows
```cmd
start.bat
```
See [WINDOWS.md](WINDOWS.md) for detailed Windows setup.

### Manual Setup

**1. Start infrastructure**
```bash
cd deploy
docker-compose up -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Initialize database**
```bash
python scripts/init_db.py
```

**4. Seed sample data**
```bash
python scripts/seed_data.py --users 1000 --days 30
```

**5. Start API**
```bash
uvicorn api.main:app --reload
# OR for production:
uvicorn api.main:app --workers 4
```

## Testing

### Unit Tests
```bash
pytest tests/ -v
pytest tests/ --cov=. --cov-report=html
```

### Load Testing
```bash
# Web UI
locust -f tests/load_test.py --host http://localhost:8000

# Headless
locust -f tests/load_test.py \
  --host http://localhost:8000 \
  --users 1000 \
  --spawn-rate 100 \
  --run-time 5m \
  --headless
```

### Performance Benchmark
```bash
python scripts/benchmark.py
```

## API Usage

### Register Feature
```bash
curl -X POST http://localhost:8000/api/v1/features/register \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user_lifetime_value",
    "version": 1,
    "dtype": "float64",
    "entity_type": "user",
    "ttl_hours": 24
  }'
```

### Get Online Features (Low Latency)
```bash
curl -X POST http://localhost:8000/api/v1/features/online \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "user_123",
    "feature_names": ["user_age", "user_lifetime_value"]
  }'
```

### Get Batch Features (Training Data)
```bash
curl -X POST http://localhost:8000/api/v1/features/batch \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_ids": ["user_1", "user_2", "user_3"],
    "feature_names": ["user_age", "user_lifetime_value"],
    "timestamp": "2024-01-15T10:00:00Z"
  }'
```

## Kubernetes Deployment

### Build and Push Image
```bash
docker build -t your-registry/feature-store:1.0.0 -f deploy/Dockerfile .
docker push your-registry/feature-store:1.0.0
```

### Deploy
```bash
# Update image in deploy/k8s/api-deployment.yaml
# Update secrets in deploy/k8s/configmap.yaml

kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/api-service.yaml
```

### Verify
```bash
kubectl get pods -l app=feature-store
kubectl get svc feature-store-api
kubectl logs -f deployment/feature-store-api
```

## Access Points

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## Using Makefile

```bash
make help           # Show all commands
make install        # Install dependencies
make test           # Run tests
make docker-up      # Start services
make init-db        # Initialize database
make seed-data      # Generate sample data
make benchmark      # Run performance tests
make run-api        # Start API (dev mode)
make run-api-prod   # Start API (production)
```

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
# Edit .env with your settings
```

Key settings:
- `POSTGRES_URL` - Database connection string
- `REDIS_URL` - Redis connection string
- `KAFKA_BROKERS` - Kafka broker addresses
- `API_KEY_SECRET` - Secret for API keys
- `LOG_LEVEL` - Logging level (INFO, DEBUG)

## Production Checklist

Before deploying to production:

1. Change default passwords and API keys
2. Enable TLS/HTTPS
3. Set up secret management (K8s secrets, Vault)
4. Configure backups for PostgreSQL
5. Set up alerting (Prometheus Alertmanager)
6. Configure log aggregation
7. Perform security audit
8. Load test at expected scale
9. Set up monitoring dashboards
10. Document runbooks

## Performance Targets

- P50 Latency: <10ms
- P99 Latency: <15ms
- Throughput: 500K features/sec
- Cache Hit Rate: >85%
- Availability: 99.9%

Verify with: `python scripts/benchmark.py`
