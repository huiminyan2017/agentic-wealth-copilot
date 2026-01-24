"""FastAPI application entrypoint.

This module defines the FastAPI app used by the Agentic Wealth Copilot backend.
It exposes a simple health endpoint and lays the groundwork for adding API
routes as the project evolves.  The application factory pattern is used so
that the app can be created with different settings for testing, development
and production.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.app.logging import configure_logging
from backend.app.services.paths import ensure_dirs
from backend.app.services.stock_scheduler import start_scheduler, stop_scheduler
from backend.app.routes.health import router as health_router
from backend.app.routes.copilot import router as copilot_router
from backend.app.routes.income import router as income_router
from backend.app.routes.spending import router as spending_router
from backend.app.routes.stocks import router as stocks_router
from backend.app.routes.alerts import router as alerts_router
from backend.app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The application sets up logging, ensures data directories exist, and
    registers routers for health and copilot endpoints.
    """
    load_dotenv()
    configure_logging()
    ensure_dirs()

    app = FastAPI(
        title="Agentic Wealth Copilot API",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Register routes
    app.include_router(income_router, prefix=settings.api_prefix, tags=["income"])
    app.include_router(spending_router, prefix=settings.api_prefix, tags=["spending"])
    app.include_router(stocks_router, prefix=settings.api_prefix, tags=["stocks"])
    app.include_router(alerts_router, prefix=settings.api_prefix, tags=["alerts"])
    app.include_router(health_router, tags=["health"])
    app.include_router(copilot_router, prefix=settings.api_prefix, tags=["copilot"])

    return app


app = create_app()
