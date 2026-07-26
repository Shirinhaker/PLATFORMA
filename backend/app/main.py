from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.cache.client import RedisClient
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, request_id_context
from app.db.session import Database
from app.media.router import router as media_router
from app.media.storage import build_r2_storage
from app.platform.router import router as platform_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.service_name, resolved.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(resolved.database_url)
        redis_client = RedisClient(resolved.redis_url)
        await database.start()
        await redis_client.start()
        app.state.database = database
        app.state.redis = redis_client
        try:
            yield
        finally:
            await redis_client.stop()
            await database.stop()

    app = FastAPI(
        title="Ko‘prik API",
        version="1.0.0",
        lifespan=lifespan,
    )
    if resolved.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestIdMiddleware)
    app.state.settings = resolved
    app.state.r2 = build_r2_storage(resolved)
    app.include_router(platform_router)
    app.include_router(media_router)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id_context.get(),
            },
        )

    return app


app = create_app()
