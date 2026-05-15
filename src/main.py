from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.cases import router as cases_router
from src.config import get_settings
from src.logging_setup import configure_logging, get_logger


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

    images_dir = settings.images_dir
    if images_dir.is_dir():
        app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")
        images_mounted = True
    else:
        # Don't crash the app just because the heavy image set isn't extracted.
        # The /cases/{id}/images endpoint already returns [] in this case.
        logger.warning(
            "images_dir_missing",
            extra={"extra_fields": {
                "event": "images_dir_missing",
                "images_dir": str(images_dir),
                "hint": "Extract MRI/SVS patches here or set IMAGES_DIR; /images is disabled until then.",
            }},
        )
        images_mounted = False

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info(
        "app_startup",
        extra={"extra_fields": {
            "event": "app_startup",
            "db_path": str(settings.db_path),
            "images_dir": str(images_dir),
            "images_mounted": images_mounted,
        }},
    )
    return app


app = create_app()
