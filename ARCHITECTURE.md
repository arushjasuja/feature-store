# Feature Store Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATIONS                         │
│  (ML Models, Data Scientists, Analytics Tools, Batch Jobs)         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTPS / REST API
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                      FASTAPI GATEWAY                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Auth         │  │ Rate         │  │ Metrics      │             │
│  │ Middleware   │  │ Limiting     │  │ Collection   │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Online       │  │ Batch        │  │ Registration │             │
│  │ Serving      │  │ Serving      │  │ Management   │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└────────┬──────────────────────────────────┬─────────────────────────┘
         │                                  │
         │                                  │
         ▼                                  ▼
┌─────────────────┐              ┌────────────────────┐
│  REDIS CACHE    │              │  POSTGRESQL +      │
│                 │              │  TIMESCALEDB       │
│  • Hot Features │◄─────────────┤                    │
│  • LRU Eviction │  Cache Miss  │  • Feature Values  │
│  • TTL: 1hr     │  Fallback    │  • Feature Registry│
│  • Msgpack      │              │  • Point-in-Time   │
│  • 85%+ Hit Rate│              │  • Compression     │
└─────────────────┘              └─────────┬──────────┘
         ▲                                  ▲
         │                                  │
         │      ┌───────────────────────────┘
         │      │
         │      │ Batch Write
         │      │
┌────────┴──────┴─────────────────────────────────────────────┐
│              STREAM PROCESSING LAYER                         │
│                                                               │
│  ┌───────────────┐       ┌─────────────────┐                │
│  │  KAFKA        │       │  SPARK          │                │
│  │  TOPICS       │──────►│  STREAMING      │                │
│  │               │       │                 │                │
│  │ • Raw Events  │       │ • Windowed Agg  │                │
│  │ • Partitioned │       │ • Transformations│               │
│  │ • 500K/sec    │       │ • Feature Compute│               │
│  └───────────────┘       └─────────────────┘                │
│         ▲                                                     │
│         │                                                     │
│         │ Event Ingestion                                    │
│         │                                                     │
└─────────┴─────────────────────────────────────────────────────┘
          │
          │
┌─────────┴─────────────────────────────────────────────────────┐
│                  EVENT PRODUCERS                              │
│  (Applications, Services, Microservices, ETL Jobs)            │
└───────────────────────────────────────────────────────────────┘


        ┌────────────────────────────────────────┐
        │     MONITORING & OBSERVABILITY         │
        │                                         │
        │  ┌──────────┐      ┌──────────────┐   │
        │  │Prometheus│◄─────┤   Grafana    │   │
        │  │  Metrics │      │  Dashboards  │   │
        │  └──────────┘      └──────────────┘   │
        │       ▲                                 │
        │       │ /metrics endpoint              │
        │       │                                 │
        └───────┼─────────────────────────────────┘
                │
        ┌───────┴──────────────────────────────────────┐
        │  Structured JSON Logs                        │
        │  (ELK Stack, CloudWatch, Datadog)            │
        └──────────────────────────────────────────────┘
```

## Data Flow

### 1. Online Feature Serving (Real-time)

```
┌────────┐     ┌─────────┐     ┌───────┐     ┌──────────┐
│ Client │────►│  API    │────►│ Redis │────►│ Response │
│        │     │ Gateway │  ┌──│ Cache │  ┌──│  <10ms   │
└────────┘     └─────────┘  │  └───────┘  │  └──────────┘
                             │             │
                             │ Cache Miss  │
                             │             │
                             │  ┌─────────┐│
                             └─►│PostgreSQL││
                                │TimescaleDB
                                └──────────┘
```

### 2. Batch Feature Serving (Training Data)

```
┌──────────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
│ Training │────►│  API    │────►│PostgreSQL│────►│ Feature  │
│   Job    │     │ Gateway │     │ (Point-  │     │  Matrix  │
│          │     │         │     │ in-Time) │     │          │
└──────────┘     └─────────┘     └──────────┘     └──────────┘
```

### 3. Stream Processing (Feature Computation)

```
┌─────────┐     ┌───────┐     ┌───────┐     ┌──────────┐
│  Event  │────►│ Kafka │────►│ Spark │────►│PostgreSQL│
│Producers│     │Topics │     │Stream │  ┌──│  +Redis  │
└─────────┘     └───────┘     │       │  │  └──────────┘
                               │5-min  │  │
                               │Window │  │ Batch Write
                               └───────┘  │
```

## Component Details

### API Layer (FastAPI)

**Purpose**: REST API for feature serving and management

**Key Features**:
- Multi-tenant authentication (API keys)
- Request validation (Pydantic)
- Async I/O for high concurrency
- Health checks and metrics
- Rate limiting (TODO)

**Endpoints**:
```
POST   /api/v1/features/online     - Get features (low latency)
POST   /api/v1/features/batch      - Get features (many entities)
POST   /api/v1/features/register   - Register feature schema
GET    /api/v1/features             - List all features
GET    /api/v1/features/{name}     - Get feature metadata
DELETE /api/v1/cache/invalidate/{entity_id} - Invalidate cache
GET    /health                      - Health check
GET    /ready                       - Readiness check
GET    /metrics                     - Prometheus metrics
```

**Performance**:
- 4 workers (adjustable)
- Connection pooling
- Async database queries
- Redis pipelining

### Storage Layer

#### Redis Cache

**Purpose**: Low-latency feature serving

**Configuration**:
- Memory: 1GB (adjustable)
- Eviction: allkeys-lru
- Persistence: Disabled (cache only)
- Serialization: msgpack (faster than JSON)

**Key Pattern**:
```
{entity_id}:{feature_name} → {value, timestamp, freshness_seconds}
```

**TTL**: 1 hour default (configurable per feature)

#### PostgreSQL + TimescaleDB

**Purpose**: Durable feature storage with time-series optimizations

**Key Features**:
- Hypertables for time-series data
- Automatic partitioning by time
- Compression (7+ days old)
- Retention policies (90 days)
- Point-in-time correctness
- Continuous aggregates

**Schema**:
```sql
-- Feature registry
features (
    id, name, version, dtype,
    entity_type, ttl_hours,
    description, tags
)

-- Time-series feature values
feature_values (
    feature_id, entity_id, timestamp,
    value (JSONB), metadata (JSONB)
)
```

**Indexes**:
- (entity_id, feature_id, timestamp DESC) - Fast lookups
- (feature_id, timestamp DESC) - Time-range queries
- GIN on JSONB columns - Flexible queries

### Stream Processing

#### Kafka

**Purpose**: Event ingestion and buffering

**Configuration**:
- Topic: feature_events
- Partitions: Configurable (default: topic auto-create)
- Replication: 1 (increase for production)
- Retention: 7 days

**Event Schema**:
```json
{
    "entity_id": "user_123",
    "event_type": "purchase",
    "value": 99.99,
    "timestamp": "2024-01-15T14:22:00Z",
    "metadata": {}
}
```

#### Spark Structured Streaming

**Purpose**: Real-time feature computation

**Operations**:
- Windowed aggregations (5-min windows, 1-min slides)
- Watermarking (10-min delay)
- Stateful transformations
- Exactly-once processing

**Output**: Batch writes to PostgreSQL and Redis

### Monitoring

#### Prometheus Metrics

**Categories**:
1. **API Metrics**: Requests, latency, errors
2. **Cache Metrics**: Hits, misses, size
3. **Database Metrics**: Query duration, pool size
4. **Feature Metrics**: Freshness, reads, writes
5. **Stream Metrics**: Lag, throughput, batch duration

**Key SLIs**:
- API P99 latency < 15ms
- Cache hit rate > 85%
- Database query P95 < 50ms
- Kafka lag < 1000 messages

#### Structured Logging

**Format**: JSON for easy parsing

**Fields**:
```json
{
    "timestamp": "2024-01-15T14:22:30",
    "level": "INFO",
    "logger": "api.routes",
    "message": "Retrieved features",
    "entity_id": "user_123",
    "feature_count": 3,
    "cache_hit": true,
    "duration_ms": 7.2
}
```

## Deployment Architecture

### Development (Docker Compose)

```
┌─────────────────────────────────────────────┐
│           Single Host (localhost)           │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │PostgreSQL│  │  Redis   │  │  Kafka   │ │
│  │   :5432  │  │  :6379   │  │  :9092   │ │
│  └──────────┘  └──────────┘  └──────────┘ │
│                                              │
│  ┌──────────┐  ┌──────────┐                │
│  │   API    │  │Prometheus│                │
│  │  :8000   │  │  :9090   │                │
│  └──────────┘  └──────────┘                │
└─────────────────────────────────────────────┘
```

### Production (Kubernetes)

```
┌──────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                 │
│                                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │              Ingress Controller                │ │
│  │              (Load Balancer)                   │ │
│  └─────────────────┬──────────────────────────────┘ │
│                    │                                 │
│  ┌─────────────────▼──────────────────────────────┐ │
│  │          API Deployment (3+ replicas)          │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │ │
│  │  │ API Pod 1│  │ API Pod 2│  │ API Pod 3│    │ │
│  │  └──────────┘  └──────────┘  └──────────┘    │ │
│  └─────────────┬────────────┬───────────────────┘ │
│                │            │                       │
│  ┌─────────────▼────────────▼───────────────────┐ │
│  │     Managed Services (AWS RDS, ElastiCache)  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │ │
│  │  │PostgreSQL│  │  Redis   │  │   MSK    │  │ │
│  │  │   RDS    │  │ElastiCache  │ (Kafka)  │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
│  ┌────────────────────────────────────────────────┐│
│  │              Monitoring Stack                  ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   ││
│  │  │Prometheus│  │  Grafana │  │Alertmanager   ││
│  │  └──────────┘  └──────────┘  └──────────┘   ││
│  └────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

## Scaling Strategies

### Horizontal Scaling

**API Layer**:
- Stateless design
- Kubernetes HPA (3-20 replicas)
- Target: 70% CPU utilization
- Each pod: 500m CPU, 1GB RAM

**Database**:
- Read replicas for read-heavy workloads
- Connection pooling (50 connections/pod)
- Query optimization and indexing

**Cache**:
- Redis Cluster for >10GB data
- Consistent hashing
- Sentinel for high availability

### Vertical Scaling

**PostgreSQL**:
- 8+ cores for production
- 32GB+ RAM for working set
- SSD storage for IOPS

**Redis**:
- Memory = working set size
- Start with 4GB, scale to 32GB+

## Security

### Authentication
- API key-based (X-API-Key header)
- Per-tenant isolation
- Key rotation policies

### Network Security
- TLS/HTTPS in production
- VPC isolation
- Security groups / Network policies
- Private subnets for databases

### Data Security
- Encryption at rest (database)
- Encryption in transit (TLS)
- Audit logging
- RBAC in Kubernetes

## Disaster Recovery

### Backup Strategy

**PostgreSQL**:
- Daily full backups
- Point-in-time recovery (WAL archiving)
- Cross-region replication
- Retention: 30 days

**Redis**:
- Cache only (no persistence needed)
- Rebuild from PostgreSQL on failure

### Recovery Procedures

**RTO (Recovery Time Objective)**: < 15 minutes
**RPO (Recovery Point Objective)**: < 5 minutes

**Failure Scenarios**:
1. API pod failure → Auto-restart (< 30s)
2. Database failure → Automatic failover (< 1 min)
3. Cache failure → Continue with database (degraded)
4. Region failure → Manual failover to secondary region

## Performance Tuning

### Database Optimization
- Analyze query plans
- Add appropriate indexes
- Partition large tables
- Adjust connection pool size
- Enable query caching

### Cache Optimization
- Monitor hit rate
- Adjust TTL per feature
- Pre-warm critical features
- Implement cache warming strategies

### API Optimization
- Increase worker count
- Use HTTP/2
- Enable response compression
- Batch database queries
- Optimize serialization

### Kafka/Spark Optimization
- Tune partition count
- Adjust batch sizes
- Configure memory allocation
- Enable checkpointing
- Monitor lag metrics

## Cost Optimization

**Development**: $20-30/month
- Small instances
- No redundancy

**Production**: $500-2000/month
- Multi-AZ deployment
- Managed services
- Monitoring stack
- Varies by scale

**Optimization Tips**:
- Use reserved instances
- Right-size compute resources
- Implement data retention policies
- Use spot instances for Spark
- Optimize database storage
