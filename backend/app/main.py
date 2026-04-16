import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


def _warn_missing_runtime_settings() -> None:
    settings = get_settings()
    missing: list[str] = []

    if settings.database_url is None:
        missing.append("DATABASE_URL")
    if settings.bank_webhook_secret is None:
        missing.append("BANK_WEBHOOK_SECRET")
    if settings.supabase_url is None and settings.supabase_jwt_secret is None:
        missing.append("SUPABASE_URL or SUPABASE_JWT_SECRET")
    if settings.env == "prod" and not settings.cors_allowed_origins:
        missing.append("CORS_ALLOWED_ORIGINS")

    if missing:
        logging.getLogger("placanje_core.startup").warning(
            "Backend is starting with missing runtime settings: %s",
            ", ".join(missing),
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    _warn_missing_runtime_settings()

    app = FastAPI(
        title="Placanje-Core Backend",
        version="0.1.0",
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url="/redoc" if settings.env != "prod" else None,
    )
    if settings.env != "prod":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/v1")
    if settings.env != "prod":
        from app.api.v1.dev import router as dev_router

        app.include_router(dev_router, prefix="/v1/dev", tags=["dev"])
    return app


app = create_app()
