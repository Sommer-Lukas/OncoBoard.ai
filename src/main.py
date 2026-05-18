from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.cases import router as cases_router
from src.api.chat import router as chat_router
from src.api.meeting import router as meeting_router
from src.api.pipeline import router as pipeline_router
from src.api.post_meeting import router as post_meeting_router
from src.logging_setup import configure_logging, get_logger


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger(__name__)

    app = FastAPI(title="OncoBoard.ai", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(cases_router)
    app.include_router(chat_router)
    app.include_router(pipeline_router)
    app.include_router(meeting_router)
    app.include_router(post_meeting_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("app_startup", extra={"extra_fields": {"event": "app_startup"}})
    return app


app = create_app()
