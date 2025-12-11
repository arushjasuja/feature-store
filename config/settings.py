from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/features"
    postgres_min_pool: int = 10
    postgres_max_pool: int = 50
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 100
    
    # Kafka
    kafka_brokers: str = "localhost:9092"
    kafka_topic: str = "feature_events"
    kafka_consumer_group: str = "feature-store"
    
    # API
    api_key_secret: str = "change-me-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    
    # Feature Store
    default_ttl_hours: int = 24
    cache_ttl_seconds: int = 3600
    
    # Monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True
    
    # Performance
    max_batch_size: int = 1000
    query_timeout_seconds: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
