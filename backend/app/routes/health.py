"""Health check endpoint.

Provides a simple endpoint to verify that the API is running.
"""

from fastapi import APIRouter

from backend.app.schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return a health status.

    Returns
    -------
    HealthResponse
        A simple status wrapper.
    """
    return HealthResponse(status="ok")