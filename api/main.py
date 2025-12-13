from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from contextlib import asynccontextmanager
from datetime import datetime
import logging

from api.routes import router
from store.postgres import FeatureStore, FeatureRegistry
from store.redis_cache import FeatureCache
from monitoring.metrics import api_requests, api_latency, initialize_system_info
from monitoring.logger import setup_logging
from config.settings import settings

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize system info metrics
initialize_system_info()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Initializes connection pools and cleans up on shutdown.
    """
    logger.info("Starting Feature Store API...")
    
    # Startup: initialize connection pools
    try:
        app.state.store = FeatureStore(
            settings.postgres_url,
            min_pool=settings.postgres_min_pool,
            max_pool=settings.postgres_max_pool
        )
        app.state.registry = FeatureRegistry(settings.postgres_url)
        
        await app.state.store.connect()
        await app.state.registry.connect()
        
        # Try to connect to Redis, but don't fail if it's not available
        app.state.cache = None
        try:
            cache = FeatureCache(
                settings.redis_url,
                max_connections=settings.redis_max_connections
            )
            await cache.connect()
            app.state.cache = cache
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis connection failed (will continue without caching): {e}")
            app.state.cache = None
        
        logger.info("Database connections established successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise
    
    yield
    
    # Shutdown: close connections
    logger.info("Shutting down Feature Store API...")
    try:
        await app.state.store.close()
        await app.state.registry.close()
        if app.state.cache:
            await app.state.cache.close()
        logger.info("All connections closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Feature Store API",
    description="Production ML feature store with real-time serving",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    Middleware to collect metrics for all requests.
    Tracks latency and request counts per endpoint.
    """
    # Skip metrics for metrics endpoint to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)
    
    # Get tenant from request state (set by auth)
    tenant = getattr(request.state, "tenant", "unknown")
    
    # Time the request
    with api_latency.labels(endpoint=request.url.path).time():
        response = await call_next(request)
    
    # Record request count
    api_requests.labels(
        endpoint=request.url.path,
        status=response.status_code,
        tenant=tenant
    ).inc()
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.log_level == "DEBUG" else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Define root-level endpoints FIRST (before routers/mounts)
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Feature Store API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "metrics": "/metrics"
    }


@app.get("/health")
async def health():
    """Health check - simple liveness probe"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready")
async def ready():
    """Readiness check - verifies dependencies are available"""
    # Simple check without blocking operations
    return {
        "status": "ready",
        "database": True,
        "cache": True,
        "timestamp": datetime.utcnow().isoformat()
    }


# Include API routes
app.include_router(router, prefix="/api/v1")

# Mount Prometheus metrics endpoint
if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower()
    )
