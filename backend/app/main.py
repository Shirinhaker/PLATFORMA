from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.advertisements.repository import AdvertisementService
from app.advertisements.router import router as advertisements_router
from app.auth.router import router as auth_router
from app.auth.shared_login import SharedLoginAuthService
from app.auth.shared_login_router import router as shared_login_router
from app.business_online.router import router as business_online_router
from app.business_online.service_relational import BusinessOnlineService
from app.cache.client import RedisClient
from app.catalog.router import router as catalog_router
from app.catalog.cache_epoch import CatalogCacheEpoch
from app.catalog.service import CatalogService
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware, request_id_context
from app.db.session import Database
from app.education.router import router as education_router
from app.education.service import EducationEnrollmentService
from app.listings.router import router as listings_router
from app.listings.service import ListingService
from app.media.router import router as media_router
from app.media.storage import build_r2_storage
from app.orders.router import router as orders_router
from app.orders.service import OrderService
from app.platform.router import router as platform_router
from app.profiles.router import router as profiles_router
from app.profiles.summary_service import ProfileSummaryService
from app.public_discovery.router import router as public_discovery_router
from app.public_discovery.service import PublicDiscoveryService
from app.queues.router import router as queues_router
from app.queues.service import QueueService
from app.staff.router import router as staff_router
from app.staff.service import StaffService


DEPLOYED_ENVIRONMENTS = {"staging", "production"}


def _validate_cors_configuration(settings: Settings) -> None:
    if (
        settings.environment in DEPLOYED_ENVIRONMENTS
        and not settings.cors_origin_list
    ):
        raise RuntimeError("cors_origins_required_for_deployed_environment")


def _remove_legacy_login_start_route() -> None:
    auth_router.routes[:] = [
        route
        for route in auth_router.routes
        if not (
            getattr(route, "path", "") == "/api/v1/auth/login/start"
            and "POST" in (getattr(route, "methods", set()) or set())
        )
    ]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    _validate_cors_configuration(resolved)
    configure_logging(resolved.service_name, resolved.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(resolved.database_url)
        redis_client = RedisClient(resolved.redis_url)
        await database.start()
        await redis_client.start()
        app.state.database = database
        app.state.redis = redis_client
        app.state.auth_service = SharedLoginAuthService(
            database.session,
            redis_client,
            resolved,
        )
        app.state.profile_summary_service = ProfileSummaryService(
            database.session,
            redis_client,
            resolved,
        )
        catalog_cache_epoch = CatalogCacheEpoch(redis_client)
        app.state.business_online_service = BusinessOnlineService(
            database.session,
            catalog_cache_epoch=catalog_cache_epoch,
        )
        app.state.public_discovery_service = PublicDiscoveryService(
            database.session,
            redis_client,
            resolved,
            image_url_provider=app.state.r2.create_download_url,
            catalog_cache_epoch=catalog_cache_epoch,
        )
        app.state.catalog_service = CatalogService(
            database.session,
            redis_client,
            resolved,
            app.state.r2.create_download_url,
            catalog_cache_epoch=catalog_cache_epoch,
        )
        app.state.listing_service = ListingService(
            database.session,
            app.state.r2.create_download_url,
            cache_epoch=catalog_cache_epoch,
        )
        app.state.advertisement_service = AdvertisementService(
            database.session,
            app.state.r2.create_download_url,
        )
        app.state.order_service = OrderService(
            database.session,
            app.state.r2.create_download_url,
        )
        app.state.queue_service = QueueService(database.session)
        app.state.education_enrollment_service = EducationEnrollmentService(
            database.session,
        )
        app.state.staff_service = StaffService(database.session, resolved)
        try:
            yield
        finally:
            await redis_client.stop()
            await database.stop()

    app = FastAPI(
        title="Koprik API",
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
    _remove_legacy_login_start_route()
    app.include_router(shared_login_router)
    app.include_router(auth_router)
    app.include_router(profiles_router)
    app.include_router(business_online_router)
    app.include_router(public_discovery_router)
    app.include_router(catalog_router)
    app.include_router(advertisements_router)
    app.include_router(listings_router)
    app.include_router(orders_router)
    app.include_router(queues_router)
    app.include_router(education_router)
    app.include_router(staff_router)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id_context.get(),
            },
            headers=exc.headers,
        )

    return app


app = create_app()
