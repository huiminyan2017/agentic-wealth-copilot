"""FastAPI application entrypoint.

This module defines the FastAPI app used by the Agentic Wealth Copilot backend.
It exposes a simple health endpoint and lays the groundwork for adding API
routes as the project evolves.  The application factory pattern is used so
that the app can be created with different settings for testing, development
and production.
"""

from fastapi import FastAPI

from backend.app.logging_conf import configure_logging
from backend.app.services.storage import ensure_dirs
from backend.app.routes.health import router as health_router
from backend.app.routes.copilot import router as copilot_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The application sets up logging, ensures data directories exist, and
    registers routers for health and copilot endpoints.
    """
    configure_logging()
    ensure_dirs()
    app = FastAPI(title="Agentic Wealth Copilot API", version="0.1.0")

    # Register routes
    app.include_router(health_router, tags=["health"])
    app.include_router(copilot_router, prefix="/api", tags=["copilot"])

    return app


app = create_app()