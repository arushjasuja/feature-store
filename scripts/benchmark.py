#!/usr/bin/env python3
"""
Benchmark script to measure Feature Store performance.
Tests latency, throughput, and cache hit rates.
"""

import asyncio
import httpx
import numpy as np
from time import time
from datetime import datetime
import statistics


class FeatureStoreBenchmark:
    """Performance benchmark suite for Feature Store"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "tenant1_key"):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
        self.results = {}
    
    async def benchmark_latency(self, num_requests: int = 1000):
        """
        Benchmark online feature serving latency.
        
        Target SLA: <10ms median, <15ms p99
        """
        print(f"\n{'='*60}")
        print(f"Latency Benchmark ({num_requests} requests)")
        print(f"{'='*60}")
        
        latencies = []
        errors = 0
        
        async with httpx.AsyncClient() as client:
            for i in range(num_requests):
                start = time()
                try:
                    response = await client.post(
                        f"{self.base_url}/api/v1/features/online",
                        json={
                            "entity_id": f"user_{i % 1000}",
                            "feature_names": ["user_age", "user_lifetime_value"]
                        },
                        headers=self.headers,
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        latency = (time() - start) * 1000  # Convert to ms
                        latencies.append(latency)
                    else:
                        errors += 1
                        
                except Exception as e:
                    errors += 1
                
                if (i + 1) % 100 == 0:
                    print(f"  Progress: {i+1}/{num_requests}")
        
        if not latencies:
            print("✗ No successful requests!")
            return
        
        # Calculate statistics
        latencies = np.array(latencies)
        results = {
            'min': np.min(latencies),
            'max': np.max(latencies),
            'mean': np.mean(latencies),
            'median': np.median(latencies),
            'p90': np.percentile(latencies, 90),
            'p95': np.percentile(latencies, 95),
            'p99': np.percentile(latencies, 99),
            'stddev': np.std(latencies),
            'errors': errors,
            'success_rate': (len(latencies) / num_requests) * 100
        }
        
        self.results['latency'] = results
        
        # Print results
        print(f"\nLatency Statistics:")
        print(f"  Min:        {results['min']:.2f}ms")
        print(f"  Max:        {results['max']:.2f}ms")
        print(f"  Mean:       {results['mean']:.2f}ms")
        print(f"  Median:     {results['median']:.2f}ms {'✓' if results['median'] < 10 else '✗ (Target: <10ms)'}")
        print(f"  P90:        {results['p90']:.2f}ms")
        print(f"  P95:        {results['p95']:.2f}ms")
        print(f"  P99:        {results['p99']:.2f}ms {'✓' if results['p99'] < 15 else '✗ (Target: <15ms)'}")
        print(f"  Std Dev:    {results['stddev']:.2f}ms")
        print(f"  Errors:     {errors}")
        print(f"  Success:    {results['success_rate']:.1f}%")
    
    async def benchmark_throughput(self, duration_seconds: int = 30):
        """
        Benchmark maximum throughput.
        
        Target: 500K features/sec
        """
        print(f"\n{'='*60}")
        print(f"Throughput Benchmark ({duration_seconds}s)")
        print(f"{'='*60}")
        
        request_count = 0
        feature_count = 0
        start_time = time()
        end_time = start_time + duration_seconds
        
        async with httpx.AsyncClient() as client:
            # Create multiple concurrent tasks
            async def make_request():
                nonlocal request_count, feature_count
                
                while time() < end_time:
                    try:
                        response = await client.post(
                            f"{self.base_url}/api/v1/features/online",
                            json={
                                "entity_id": f"user_{request_count % 1000}",
                                "feature_names": ["user_age", "user_lifetime_value", "last_purchase_days"]
                            },
                            headers=self.headers,
                            timeout=5.0
                        )
                        
                        if response.status_code == 200:
                            request_count += 1
                            feature_count += 3  # 3 features per request
                            
                    except Exception:
                        pass
            
            # Run concurrent requests
            num_workers = 100
            tasks = [make_request() for _ in range(num_workers)]
            await asyncio.gather(*tasks)
        
        elapsed = time() - start_time
        
        results = {
            'requests': request_count,
            'features': feature_count,
            'duration': elapsed,
            'requests_per_sec': request_count / elapsed,
            'features_per_sec': feature_count / elapsed
        }
        
        self.results['throughput'] = results
        
        # Print results
        print(f"\nThroughput Statistics:")
        print(f"  Total Requests:     {results['requests']:,}")
        print(f"  Total Features:     {results['features']:,}")
        print(f"  Duration:           {results['duration']:.2f}s")
        print(f"  Requests/sec:       {results['requests_per_sec']:,.2f}")
        print(f"  Features/sec:       {results['features_per_sec']:,.2f} {'✓' if results['features_per_sec'] > 500000 else '(Target: >500K)'}")
    
    async def benchmark_cache_hit_rate(self, num_requests: int = 1000):
        """
        Benchmark cache hit rate.
        
        Target: >85% cache hit rate
        """
        print(f"\n{'='*60}")
        print(f"Cache Hit Rate Benchmark ({num_requests} requests)")
        print(f"{'='*60}")
        
        cache_hits = 0
        total_requests = 0
        
        # Use a small set of entity IDs to maximize cache hits
        hot_entities = [f"user_{i}" for i in range(1, 101)]
        
        async with httpx.AsyncClient() as client:
            for i in range(num_requests):
                try:
                    # Alternate between hot and cold entities
                    if i % 10 < 8:  # 80% hot entities
                        entity_id = hot_entities[i % len(hot_entities)]
                    else:  # 20% cold entities
                        entity_id = f"user_{1000 + i}"
                    
                    response = await client.post(
                        f"{self.base_url}/api/v1/features/online",
                        json={
                            "entity_id": entity_id,
                            "feature_names": ["user_age", "user_lifetime_value"]
                        },
                        headers=self.headers,
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("cache_hit"):
                            cache_hits += 1
                        total_requests += 1
                        
                except Exception:
                    pass
                
                if (i + 1) % 100 == 0:
                    print(f"  Progress: {i+1}/{num_requests}")
        
        hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        results = {
            'cache_hits': cache_hits,
            'total_requests': total_requests,
            'hit_rate': hit_rate
        }
        
        self.results['cache'] = results
        
        # Print results
        print(f"\nCache Statistics:")
        print(f"  Cache Hits:         {cache_hits}")
        print(f"  Total Requests:     {total_requests}")
        print(f"  Hit Rate:           {hit_rate:.1f}% {'✓' if hit_rate > 85 else '✗ (Target: >85%)'}")
    
    async def benchmark_batch_performance(self):
        """Benchmark batch feature retrieval"""
        print(f"\n{'='*60}")
        print(f"Batch Performance Benchmark")
        print(f"{'='*60}")
        
        batch_sizes = [10, 50, 100, 250, 500]
        
        async with httpx.AsyncClient() as client:
            for batch_size in batch_sizes:
                entity_ids = [f"user_{i}" for i in range(1, batch_size + 1)]
                
                start = time()
                response = await client.post(
                    f"{self.base_url}/api/v1/features/batch",
                    json={
                        "entity_ids": entity_ids,
                        "feature_names": ["user_age", "user_lifetime_value"]
                    },
                    headers=self.headers,
                    timeout=30.0
                )
                elapsed = (time() - start) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"  Batch size {batch_size:3d}: {elapsed:6.2f}ms ({elapsed/batch_size:.2f}ms per entity)")
    
    def print_summary(self):
        """Print benchmark summary"""
        print(f"\n{'='*60}")
        print(f"Benchmark Summary")
        print(f"{'='*60}")
        
        if 'latency' in self.results:
            lat = self.results['latency']
            p50_ok = "✓" if lat['median'] < 10 else "✗"
            p99_ok = "✓" if lat['p99'] < 15 else "✗"
            print(f"\nLatency:")
            print(f"  P50: {lat['median']:.2f}ms {p50_ok} (Target: <10ms)")
            print(f"  P99: {lat['p99']:.2f}ms {p99_ok} (Target: <15ms)")
        
        if 'throughput' in self.results:
            thr = self.results['throughput']
            thr_ok = "✓" if thr['features_per_sec'] > 500000 else "✗"
            print(f"\nThroughput:")
            print(f"  {thr['features_per_sec']:,.0f} features/sec {thr_ok} (Target: >500K)")
        
        if 'cache' in self.results:
            cache = self.results['cache']
            cache_ok = "✓" if cache['hit_rate'] > 85 else "✗"
            print(f"\nCache Hit Rate:")
            print(f"  {cache['hit_rate']:.1f}% {cache_ok} (Target: >85%)")
        
        print(f"\n{'='*60}")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Benchmark Feature Store performance')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--api-key', default='tenant1_key', help='API key')
    parser.add_argument('--latency-requests', type=int, default=1000, help='Latency test requests')
    parser.add_argument('--throughput-duration', type=int, default=30, help='Throughput test duration (seconds)')
    parser.add_argument('--cache-requests', type=int, default=1000, help='Cache test requests')
    args = parser.parse_args()
    
    print("="*60)
    print("Feature Store Performance Benchmark")
    print("="*60)
    print(f"Target: {args.url}")
    print(f"Timestamp: {datetime.now()}")
    
    benchmark = FeatureStoreBenchmark(base_url=args.url, api_key=args.api_key)
    
    try:
        # Run benchmarks
        await benchmark.benchmark_latency(num_requests=args.latency_requests)
        await benchmark.benchmark_cache_hit_rate(num_requests=args.cache_requests)
        await benchmark.benchmark_batch_performance()
        await benchmark.benchmark_throughput(duration_seconds=args.throughput_duration)
        
        # Print summary
        benchmark.print_summary()
        
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
