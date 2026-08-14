import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@router.get("/api/v1/build")
async def build(request: Request) -> dict[str, str]:
    return {
        "api_version": "v1",
        "foundation": "phase1",
        "legacy_build": request.app.state.settings.legacy_build,
    }


@router.get("/api/v1/public/features")
async def public_features(request: Request) -> dict[str, bool]:
    settings = request.app.state.settings
    return {
        "listings": settings.listings_enabled,
        "stories": settings.stories_enabled,
        "chat": settings.chat_enabled,
        "systemization": False,
        "taxi": settings.taxi_enabled,
    }


@router.get("/readyz")
async def readyz(request: Request):
    database_ready, redis_ready = await asyncio.gather(
        request.app.state.database.ready(),
        request.app.state.redis.ready(),
    )
    settings = request.app.state.settings
    if settings.environment in {"development", "test"}:
        r2_ready = True
    else:
        r2_ready = await asyncio.to_thread(request.app.state.r2.ready)
    ready = database_ready and redis_ready and r2_ready
    payload = {
        "status": "ready" if ready else "not_ready",
        "database": database_ready,
        "redis": redis_ready,
        "r2": r2_ready,
    }
    return JSONResponse(payload, status_code=200 if ready else 503)
