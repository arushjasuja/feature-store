from fastapi import HTTPException, status, Header
from typing import Optional
import hmac
import hashlib


# In production, store API keys in database with tenant mapping
# This is a simplified version for demonstration
API_KEYS = {
    "tenant1_key": "tenant1",
    "tenant2_key": "tenant2",
    "dev_key": "development",
}


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Verify API key and return tenant ID.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        tenant_id: Tenant identifier
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    tenant_id = API_KEYS.get(x_api_key)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return tenant_id


def hash_api_key(key: str, secret: str) -> str:
    """
    Hash API key for secure storage.
    
    Args:
        key: API key to hash
        secret: Secret salt for hashing
        
    Returns:
        Hashed key
    """
    return hmac.new(
        secret.encode(),
        key.encode(),
        hashlib.sha256
    ).hexdigest()
