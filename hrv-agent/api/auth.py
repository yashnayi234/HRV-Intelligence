"""API key authentication middleware."""

from __future__ import annotations

import os

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
    """Validate the X-API-Key header against the configured secret."""
    expected = os.getenv("HRV_API_KEY", "hrv-agent-dev-key-2024")
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
