# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### Problem: `pip install` fails with compilation errors
**Solution:**
```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y python3-dev gcc g++ libpq-dev

# For macOS
brew install postgresql
```

#### Problem: `asyncpg` installation fails
**Solution:**
```bash
# Install PostgreSQL development libraries
# Ubuntu/Debian
sudo apt-get install -y libpq-dev

# macOS
brew install postgresql

# Then retry
pip install asyncpg
```

### Database Issues

#### Problem: Database connection refused
**Symptoms:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Solutions:**
1. Check PostgreSQL is running:
```bash
docker-compose ps postgres
# Should show "healthy" status
```

2. Check connection string in .env:
```bash
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/features
```

3. Restart PostgreSQL:
```bash
cd deploy
docker-compose restart postgres
```

#### Problem: TimescaleDB extension not found
**Symptoms:** `ERROR: extension "timescaledb" is not available`

**Solution:**
Use the correct Docker image with TimescaleDB:
```yaml
# In docker-compose.yml
postgres:
  image: timescale/timescaledb:latest-pg15  # Correct
  # NOT: image: postgres:15                 # Wrong
```

#### Problem: Permission denied on database operations
**Symptoms:** `permission denied for table feature_values`

**Solution:**
```sql
-- Connect to database and grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;
```

### Redis Issues

#### Problem: Redis connection timeout
**Symptoms:** `redis.exceptions.TimeoutError`

**Solutions:**
1. Check Redis is running:
```bash
docker-compose ps redis
redis-cli ping  # Should return PONG
```

2. Check Redis URL:
```bash
REDIS_URL=redis://localhost:6379/0
```

3. Clear Redis cache:
```bash
redis-cli FLUSHDB
```

#### Problem: Redis memory limit reached
**Symptoms:** `OOM command not allowed when used memory > 'maxmemory'`

**Solution:**
Increase Redis memory in docker-compose.yml:
```yaml
redis:
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### Kafka Issues

#### Problem: Kafka not starting
**Symptoms:** `Connection error: [Errno 111] Connection refused`

**Solutions:**
1. Check Zookeeper is running first:
```bash
docker-compose ps zookeeper
```

2. Restart Kafka services:
```bash
docker-compose restart zookeeper
docker-compose restart kafka
```

3. Check logs:
```bash
docker-compose logs kafka
```

#### Problem: Kafka topic not found
**Solution:**
```bash
# Create topic manually
docker-compose exec kafka kafka-topics \
  --create \
  --topic feature_events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

### API Issues

#### Problem: API not starting - Import errors
**Symptoms:** `ModuleNotFoundError: No module named 'api'`

**Solution:**
Make sure you're running from project root:
```bash
cd /path/to/feature-store
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn api.main:app --reload
```

#### Problem: API responding slowly
**Symptoms:** Latency > 100ms

**Diagnostics:**
```bash
# Check cache hit rate
curl http://localhost:8000/metrics | grep cache_hit

# Check database connections
curl http://localhost:8000/metrics | grep db_connection_pool
```

**Solutions:**
1. Pre-warm cache:
```bash
python scripts/seed_data.py --cache-users 1000
```

2. Increase connection pool:
```bash
# In .env
POSTGRES_MAX_POOL=100
```

3. Add more API workers:
```bash
uvicorn api.main:app --workers 8
```

#### Problem: Health check failing
**Symptoms:** `/ready` returns 503

**Solution:**
Check individual components:
```bash
# Test database
docker-compose exec postgres psql -U postgres -d features -c "SELECT 1"

# Test Redis
docker-compose exec redis redis-cli ping

# Check logs
docker-compose logs api
```

### Performance Issues

#### Problem: High latency on feature retrieval
**Target:** <10ms median, <15ms p99

**Diagnostics:**
```bash
python scripts/benchmark.py
```

**Solutions:**
1. Check cache hit rate (target >85%):
```bash
curl http://localhost:8000/metrics | grep cache_hit_rate
```

2. Add database indexes:
```sql
CREATE INDEX idx_custom ON feature_values (entity_id, timestamp DESC);
```

3. Optimize queries:
```sql
EXPLAIN ANALYZE SELECT * FROM feature_values WHERE entity_id = 'user_123';
```

4. Scale horizontally:
```bash
# Kubernetes
kubectl scale deployment feature-store-api --replicas=10
```

#### Problem: Low throughput
**Target:** 500K features/sec

**Solutions:**
1. Increase Kafka partitions:
```bash
kafka-topics --alter --topic feature_events --partitions 10
```

2. Tune Spark:
```python
# In spark_processor.py
.config("spark.sql.shuffle.partitions", "20")
.config("spark.streaming.kafka.maxRatePerPartition", "2000")
```

3. Use batch writes:
```python
# Write in larger batches
batch_size = 10000
```

### Testing Issues

#### Problem: Tests failing - fixture errors
**Symptoms:** `fixture 'client' not found`

**Solution:**
Install pytest-asyncio:
```bash
pip install pytest-asyncio
```

Configure pytest.ini:
```ini
[pytest]
asyncio_mode = auto
```

#### Problem: Load tests not connecting
**Symptoms:** Connection errors in Locust

**Solution:**
1. Verify API is running:
```bash
curl http://localhost:8000/health
```

2. Check API key:
```bash
# In tests/load_test.py
headers = {"X-API-Key": "tenant1_key"}
```

3. Start load test correctly:
```bash
locust -f tests/load_test.py --host http://localhost:8000
```

### Docker Issues

#### Problem: Port already in use
**Symptoms:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solutions:**
1. Find process using port:
```bash
lsof -i :8000
kill -9 <PID>
```

2. Change port in docker-compose.yml:
```yaml
ports:
  - "8001:8000"  # External:Internal
```

#### Problem: Out of disk space
**Symptoms:** `no space left on device`

**Solutions:**
1. Clean Docker:
```bash
docker system prune -a --volumes
```

2. Clean Python cache:
```bash
make clean
```

3. Check disk usage:
```bash
docker system df
df -h
```

#### Problem: Services won't start - depends_on not working
**Solution:**
Wait for services to be healthy:
```bash
# Check status
docker-compose ps

# Wait for all healthy
while ! docker-compose ps | grep -q "healthy"; do
  sleep 5
done
```

### Development Issues

#### Problem: Code changes not reflected
**Solution:**
Use reload mode:
```bash
uvicorn api.main:app --reload
```

#### Problem: Import errors in development
**Solution:**
Install in editable mode:
```bash
pip install -e .
```

### Monitoring Issues

#### Problem: Prometheus not scraping metrics
**Symptoms:** No data in Prometheus

**Solutions:**
1. Check metrics endpoint:
```bash
curl http://localhost:8000/metrics
```

2. Verify prometheus.yml:
```yaml
scrape_configs:
  - job_name: 'feature-store-api'
    static_configs:
      - targets: ['api:8000']  # Use service name in Docker
```

3. Restart Prometheus:
```bash
docker-compose restart prometheus
```

#### Problem: Grafana showing no data
**Solutions:**
1. Add Prometheus as data source in Grafana:
   - URL: http://prometheus:9090
   - Access: Server (default)

2. Import dashboard from JSON

## Getting Help

If you're still experiencing issues:

1. Check logs:
```bash
# API logs
docker-compose logs -f api

# All logs
docker-compose logs -f

# Specific service
docker-compose logs postgres
```

2. Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG
```

3. Run diagnostics:
```bash
# Check all services
docker-compose ps

# Test connections
python scripts/init_db.py

# Run benchmark
python scripts/benchmark.py
```

4. Report issue:
   - Collect logs
   - Note your environment (OS, Python version, Docker version)
   - Describe steps to reproduce
   - Include error messages

## Quick Fixes

### Nuclear Option - Clean Restart
```bash
# Stop everything
docker-compose down -v

# Clean Python cache
make clean

# Restart
docker-compose up -d

# Reinitialize
python scripts/init_db.py
python scripts/seed_data.py
```

### Quick Health Check
```bash
# Check all services are healthy
docker-compose ps

# Test API
curl http://localhost:8000/health

# Test database
docker-compose exec postgres psql -U postgres -d features -c "SELECT COUNT(*) FROM features"

# Test cache
docker-compose exec redis redis-cli ping

# Test feature retrieval
curl -X POST http://localhost:8000/api/v1/features/online \
  -H "X-API-Key: tenant1_key" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "user_1", "feature_names": ["user_age"]}'
```
