from fastapi import FastAPI

from src.config import get_settings
from src.logging_setup import configure_logging, get_logger


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()

    app = FastAPI(title="OncoBoard.ai", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info(
        "app_startup",
        extra={"extra_fields": {"event": "app_startup", "db_path": str(settings.db_path)}},
    )
    return app


app = create_app()
