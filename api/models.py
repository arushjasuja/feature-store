from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any
from datetime import datetime


class OnlineFeatureRequest(BaseModel):
    """Request model for online feature serving"""
    entity_id: str = Field(..., min_length=1, description="Entity identifier (e.g., user_123)")
    feature_names: List[str] = Field(..., min_length=1, description="List of feature names to retrieve")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "user_12345",
                "feature_names": ["age", "lifetime_value", "last_purchase_days"]
            }
        }
    )


class FeatureValue(BaseModel):
    """Individual feature value with metadata"""
    value: Any = Field(..., description="Feature value")
    timestamp: datetime = Field(..., description="When the feature was computed")
    freshness_seconds: Optional[float] = Field(None, description="Age of feature in seconds")


class OnlineFeatureResponse(BaseModel):
    """Response model for online feature serving"""
    entity_id: str
    features: Dict[str, FeatureValue]
    timestamp: datetime
    source: str = Field(default="NOT_SET", description="Data source: cache or database")
    cache_hit: bool = Field(default=False, description="Whether response was served from cache")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "user_123",
                "features": {
                    "age": {"value": 42, "timestamp": "2024-01-01T00:00:00Z", "freshness_seconds": 5.2}
                },
                "timestamp": "2024-01-01T00:00:00Z",
                "source": "cache",
                "cache_hit": True
            }
        }
    )


class BatchFeatureRequest(BaseModel):
    """Request model for batch feature serving"""
    entity_ids: List[str] = Field(..., min_length=1, max_length=1000, description="List of entity identifiers")
    feature_names: List[str] = Field(..., min_length=1, description="List of feature names to retrieve")
    timestamp: Optional[datetime] = Field(None, description="Point-in-time timestamp for historical features")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_ids": ["user_123", "user_456"],
                "feature_names": ["age", "lifetime_value"],
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )


class BatchFeatureResponse(BaseModel):
    """Response model for batch feature serving"""
    features: Dict[str, Dict[str, FeatureValue]]  # entity_id -> feature_name -> value
    timestamp: datetime
    count: int = Field(..., description="Number of entities returned")


class FeatureSchema(BaseModel):
    """Schema for feature registration"""
    name: str = Field(..., description="Feature name", min_length=1, max_length=255)
    version: int = Field(1, description="Feature version", ge=1)
    dtype: str = Field(..., description="Data type (float64, int64, string, bool)")
    entity_type: str = Field(..., description="Entity type (user, product, session, etc)")
    ttl_hours: int = Field(24, description="Time-to-live in hours", ge=1)
    description: str = Field("", description="Human-readable feature description")
    tags: Optional[List[str]] = Field(None, description="Tags for feature discovery")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "user_lifetime_value",
                "version": 2,
                "dtype": "float64",
                "entity_type": "user",
                "ttl_hours": 24,
                "description": "Predicted customer lifetime value in USD",
                "tags": ["revenue", "prediction"]
            }
        }
    )


class FeatureRegistrationResponse(BaseModel):
    """Response after feature registration"""
    feature_id: int
    name: str
    version: int
    status: str = "registered"
    created_at: datetime


class FeatureMetadata(BaseModel):
    """Metadata about a registered feature"""
    id: int
    name: str
    version: int
    dtype: str
    entity_type: str
    ttl_hours: int
    description: str
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class FeatureListResponse(BaseModel):
    """Response with list of features"""
    features: List[FeatureMetadata]
    count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str = "1.0.0"


class ReadinessResponse(BaseModel):
    """Readiness check response"""
    status: str
    database: bool
    cache: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime
