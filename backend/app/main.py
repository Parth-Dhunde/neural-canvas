"""NeuralCanvas FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.paths import get_workspace_root
from app.schemas.common import HealthResponse, RootResponse, VersionResponse
from app.services.system_status import log_startup_validation, run_startup_validation

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown hooks."""
    setup_logging()
    settings = get_settings()
    logger.info("Starting %s v%s", settings.app_name, __version__)
    logger.info("Workspace root: %s", get_workspace_root())
    validation = run_startup_validation(settings)
    log_startup_validation(validation, logger)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=RootResponse, tags=["root"])
    async def root() -> RootResponse:
        """Root endpoint with basic service metadata."""
        return RootResponse(
            app=settings.app_name,
            status="ok",
            docs="/docs",
        )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Liveness probe used by the frontend backend status indicator."""
        return HealthResponse(status="ok")

    @app.get("/version", response_model=VersionResponse, tags=["health"])
    async def version() -> VersionResponse:
        """Return the running application version."""
        return VersionResponse(version=__version__, app=settings.app_name)

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
