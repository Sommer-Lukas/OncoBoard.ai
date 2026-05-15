from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.cases import router as cases_router
from src.config import get_settings
from src.logging_setup import configure_logging, get_logger

_IMAGES_DIR = "src/data/MRI_and_SVS_Patches/MRI_and_SVS_Patches"


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()

    app = FastAPI(title="OncoBoard.ai", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(cases_router)
    app.mount("/images", StaticFiles(directory=_IMAGES_DIR), name="images")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info(
        "app_startup",
        extra={"extra_fields": {"event": "app_startup", "db_path": str(settings.db_path)}},
    )
    return app


app = create_app()
