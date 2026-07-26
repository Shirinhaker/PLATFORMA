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


@router.get("/readyz")
async def readyz(request: Request):
    database_ready = await request.app.state.database.ready()
    redis_ready = await request.app.state.redis.ready()
    settings = request.app.state.settings
    r2_configured = (
        settings.environment in {"development", "test"}
        or bool(
            settings.r2_bucket
            and settings.r2_access_key_id
            and settings.r2_secret_access_key
        )
    )
    ready = database_ready and redis_ready and r2_configured
    payload = {
        "status": "ready" if ready else "not_ready",
        "database": database_ready,
        "redis": redis_ready,
        "r2_configured": r2_configured,
    }
    return JSONResponse(payload, status_code=200 if ready else 503)
