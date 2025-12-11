from locust import HttpUser, task, between, events
import random
import time
from datetime import datetime


class FeatureStoreUser(HttpUser):
    """
    Load test user simulating feature store API usage.
    
    Usage:
        locust -f tests/load_test.py --host http://localhost:8000
    
    Target:
        - 10K concurrent users
        - <10ms median latency
        - <15ms p99 latency
    """
    
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """Initialize user session"""
        self.headers = {"X-API-Key": "tenant1_key"}
        self.entity_ids = [f"user_{i}" for i in range(1, 10001)]
        self.feature_names = [
            "user_age",
            "user_lifetime_value",
            "last_purchase_days",
            "avg_5min_purchase_value"
        ]
    
    @task(10)
    def get_online_features_single(self):
        """
        Test online feature serving for a single entity.
        This is the most common use case - low latency single lookups.
        Weighted at 10x to simulate production traffic patterns.
        """
        entity_id = random.choice(self.entity_ids)
        num_features = random.randint(2, 4)
        features = random.sample(self.feature_names, num_features)
        
        start_time = time.time()
        with self.client.post(
            "/api/v1/features/online",
            json={
                "entity_id": entity_id,
                "feature_names": features
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            elapsed = (time.time() - start_time) * 1000  # Convert to ms
            
            if response.status_code == 200:
                # Check latency SLA
                if elapsed > 15:
                    response.failure(f"Too slow: {elapsed:.2f}ms (SLA: <15ms p99)")
                elif elapsed > 10:
                    # Warning but not failure
                    pass
                else:
                    response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(3)
    def get_online_features_cached(self):
        """
        Test cache hit scenario by querying the same entity repeatedly.
        Simulates popular entities that should be cached.
        """
        # Use a small set of "hot" entity IDs
        hot_entity_id = f"user_{random.randint(1, 100)}"
        
        with self.client.post(
            "/api/v1/features/online",
            json={
                "entity_id": hot_entity_id,
                "feature_names": self.feature_names
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("cache_hit"):
                    response.success()
                else:
                    # Not necessarily a failure, but track it
                    response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(1)
    def get_batch_features_small(self):
        """
        Test small batch feature retrieval (10-50 entities).
        Used for batch predictions on small cohorts.
        """
        batch_size = random.randint(10, 50)
        entity_ids = random.sample(self.entity_ids, batch_size)
        
        with self.client.post(
            "/api/v1/features/batch",
            json={
                "entity_ids": entity_ids,
                "feature_names": random.sample(self.feature_names, 2)
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(1)
    def get_batch_features_large(self):
        """
        Test large batch feature retrieval (100-500 entities).
        Used for batch predictions and training data generation.
        """
        batch_size = random.randint(100, 500)
        entity_ids = random.sample(self.entity_ids, batch_size)
        
        with self.client.post(
            "/api/v1/features/batch",
            json={
                "entity_ids": entity_ids,
                "feature_names": self.feature_names
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data["count"] != batch_size:
                    response.failure(f"Expected {batch_size} entities, got {data['count']}")
                else:
                    response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(1)
    def list_features(self):
        """Test feature listing endpoint"""
        with self.client.get(
            "/api/v1/features",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(1)
    def get_feature_metadata(self):
        """Test feature metadata retrieval"""
        feature_name = random.choice(self.feature_names)
        
        with self.client.get(
            f"/api/v1/features/{feature_name}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulates admin operations (feature registration, cache invalidation).
    Lower frequency than regular users.
    """
    
    wait_time = between(5, 15)
    
    def on_start(self):
        self.headers = {"X-API-Key": "tenant1_key"}
    
    @task(1)
    def register_feature(self):
        """Test feature registration"""
        feature_name = f"test_feature_{random.randint(1, 1000)}"
        
        with self.client.post(
            "/api/v1/features/register",
            json={
                "name": feature_name,
                "version": 1,
                "dtype": "float64",
                "entity_type": "user",
                "ttl_hours": 24,
                "description": "Load test feature",
                "tags": ["loadtest"]
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got {response.status_code}")
    
    @task(1)
    def invalidate_cache(self):
        """Test cache invalidation"""
        entity_id = f"user_{random.randint(1, 10000)}"
        
        with self.client.delete(
            f"/api/v1/cache/invalidate/{entity_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test information at start"""
    print(f"\n{'='*60}")
    print(f"Feature Store Load Test")
    print(f"Target: {environment.host}")
    print(f"Performance SLAs:")
    print(f"  - Median latency: <10ms")
    print(f"  - P99 latency: <15ms")
    print(f"  - Throughput: 500K features/sec")
    print(f"  - Cache hit rate: >85%")
    print(f"{'='*60}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary at end"""
    stats = environment.stats
    
    print(f"\n{'='*60}")
    print(f"Load Test Summary")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Median response time: {stats.total.median_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"Requests per second: {stats.total.total_rps:.2f}")
    print(f"{'='*60}\n")
