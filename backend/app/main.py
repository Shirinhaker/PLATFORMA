from contextlib import asynccontextmanager
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.advertisements.repository import AdvertisementService
from app.advertisements.authoring_router import (
    router as advertisement_authoring_router,
)
from app.advertisements.router import router as advertisements_router
from app.advertisements.service import AdvertisementAuthoringService
from app.account_settings.router import router as account_settings_router
from app.account_settings.service import AccountSettingsService
from app.auth.router import router as auth_router
from app.auth.shared_login import SharedLoginAuthService
from app.auth.shared_login_router import router as shared_login_router
from app.ai_assistant.provider import OpenAIResponsesProvider
from app.ai_assistant.router import router as ai_assistant_router
from app.ai_assistant.service import AIAssistantService
from app.business_online.router import router as business_online_router
from app.business_online.service_relational import BusinessOnlineService
from app.business_opening.router import router as business_opening_router
from app.business_opening.service import BusinessOpeningService
from app.cash_register.router import router as cash_register_router
from app.cash_register.service import CashRegisterService
from app.cache.client import RedisClient
from app.catalog.router import router as catalog_router
from app.catalog.cache_epoch import CatalogCacheEpoch
from app.catalog.service import CatalogService
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.core.middleware import MetricsMiddleware, RequestIdMiddleware, request_id_context
from app.db.session import Database
from app.admin.moderation_service import AdminModerationService
from app.admin.payments_service import AdminPaymentService
from app.admin.reports_service import AdminReportsService
from app.admin.reports_router import router as reports_router
from app.admin.router import router as admin_router
from app.admin.service import AdminAuthService
from app.debt_ledger.router import router as debt_ledger_router
from app.debt_ledger.service import DebtLedgerService
from app.dining.router import router as dining_router
from app.dining.service import DiningService
from app.documents.router import router as documents_router
from app.documents.service import DocumentService
from app.education.router import router as education_router
from app.education.management_service import EducationManagementService
from app.education.service import EducationEnrollmentService
from app.education.repository import EducationEnrollmentRepository
from app.education.statistics_service import EducationStatisticsService
from app.expenses.router import router as expenses_router
from app.expenses.service import ExpenseService
from app.inventory.router import router as inventory_router
from app.inventory.service import InventoryService
from app.listings.activation import ListingActivationService
from app.listings.router import router as listings_router
from app.listings.service import ListingService
from app.media.router import router as media_router
from app.media.storage import build_r2_storage
from app.messages.router import router as messages_router
from app.messages.service import MessageService
from app.notifications.router import router as notifications_router
from app.notifications.service import NotificationService
from app.orders.router import router as orders_router
from app.orders.service import OrderService
from app.platform.router import router as platform_router
from app.profiles.router import router as profiles_router
from app.profiles.summary_service import ProfileSummaryService
from app.public_discovery.router import router as public_discovery_router
from app.public_discovery.service import PublicDiscoveryService
from app.follows.router import router as follows_router
from app.follows.service import FollowService
from app.payments.router import router as payments_router
from app.payments.service import PaymentService
from app.queues.router import router as queues_router
from app.queues.service import QueueService
from app.reviews.router import router as reviews_router
from app.reviews.service import ReviewService
from app.staff.router import router as staff_router
from app.staff.service import StaffService
from app.statistics.router import router as statistics_router
from app.statistics.service import StatisticsService
from app.stories.router import router as stories_router
from app.stories.service import StoryService
from app.specialists.router import router as specialists_router
from app.specialists.service import SpecialistService
from app.taxi.admin_router import router as taxi_admin_router
from app.taxi.router import router as taxi_router
from app.taxi.service import TaxiService


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
        database = Database(
            resolved.database_url,
            pool_size=resolved.db_pool_size,
            max_overflow=resolved.db_max_overflow,
            pool_timeout=resolved.db_pool_timeout_seconds,
        )
        redis_client = RedisClient(
            resolved.redis_url,
            max_connections=resolved.redis_max_connections,
        )
        await database.start()
        await redis_client.start()
        app.state.database = database
        app.state.redis = redis_client
        app.state.auth_service = SharedLoginAuthService(
            database.session,
            redis_client,
            resolved,
        )
        app.state.account_settings_service = AccountSettingsService(
            database.session,
        )
        app.state.business_opening_service = BusinessOpeningService(
            database.session,
            resolved,
        )
        app.state.profile_summary_service = ProfileSummaryService(
            database.session,
            redis_client,
            resolved,
        )
        catalog_cache_epoch = CatalogCacheEpoch(redis_client)
        education_repository = EducationEnrollmentRepository(
            legacy_json_compatibility=resolved.environment == "test",
        )
        app.state.business_online_service = BusinessOnlineService(
            database.session,
            catalog_cache_epoch=catalog_cache_epoch,
            education_repository=education_repository,
            legacy_json_compatibility=resolved.environment == "test",
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
        app.state.expense_service = ExpenseService(database.session)
        app.state.inventory_service = InventoryService(
            database.session,
            expense_service=app.state.expense_service,
        )
        app.state.debt_ledger_service = DebtLedgerService(database.session)
        app.state.cash_register_service = CashRegisterService(
            database.session,
            inventory_service=app.state.inventory_service,
            debt_ledger_service=app.state.debt_ledger_service,
        )
        app.state.taxi_service = TaxiService(database.session)
        app.state.order_service = OrderService(
            database.session,
            app.state.r2.create_download_url,
            cash_register_service=app.state.cash_register_service,
            debt_ledger_service=app.state.debt_ledger_service,
            taxi_service=app.state.taxi_service,
        )
        app.state.message_service = MessageService(
            database.session,
            app.state.r2.create_download_url,
        )
        app.state.review_service = ReviewService(database.session)
        app.state.notification_service = NotificationService(
            database.session,
            push_configured=bool(
                resolved.firebase_service_account_json
                or resolved.firebase_service_account_path
                or os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
                or os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
            ),
        )
        app.state.dining_service = DiningService(
            database.session,
            inventory=app.state.inventory_service,
            debt_ledger=app.state.debt_ledger_service,
        )
        app.state.document_service = DocumentService(database.session)
        app.state.ai_assistant_service = AIAssistantService(
            database.session,
            OpenAIResponsesProvider(
                api_key=resolved.openai_api_key or os.environ.get("OPENAI_API_KEY", ""),
                model=os.environ.get("OPENAI_MODEL", resolved.openai_model),
                timeout_seconds=resolved.openai_timeout_seconds,
            ),
        )
        app.state.follow_service = FollowService(
            database.session,
            image_url_provider=app.state.r2.create_download_url,
        )
        app.state.story_service = StoryService(
            database.session,
            app.state.r2,
        )
        app.state.specialist_service = SpecialistService(
            database.session,
            image_url_provider=app.state.r2.create_download_url,
            object_deleter=app.state.r2.delete_object,
        )
        app.state.listing_activation_service = ListingActivationService(
            database.session,
            notification_service=app.state.notification_service,
        )
        app.state.advertisement_authoring_service = AdvertisementAuthoringService(
            database.session,
            image_url_provider=app.state.r2.create_download_url,
        )
        app.state.payment_service = PaymentService(
            database.session,
            download_url_provider=app.state.r2.create_download_url,
            advertisement_service=app.state.advertisement_authoring_service,
            listing_service=app.state.listing_activation_service,
        )
        app.state.admin_auth_service = AdminAuthService(
            database.session, resolved
        )
        app.state.admin_payment_service = AdminPaymentService(
            database.session,
            now=lambda: int(time.time()),
            download_url_provider=app.state.r2.create_download_url,
        )
        app.state.admin_moderation_service = AdminModerationService(
            database.session
        )
        app.state.admin_reports_service = AdminReportsService(
            database.session
        )
        app.state.queue_service = QueueService(database.session)
        app.state.education_enrollment_service = EducationEnrollmentService(
            database.session,
            repository=education_repository,
        )
        app.state.education_statistics_service = EducationStatisticsService(
            database.session,
        )
        app.state.education_management_service = EducationManagementService(
            database.session,
            enrollment_repository=education_repository,
        )
        app.state.staff_service = StaffService(database.session, resolved)
        app.state.statistics_service = StatisticsService(database.session)
        try:
            yield
        finally:
            await app.state.ai_assistant_service.close()
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
    app.add_middleware(MetricsMiddleware)
    app.state.settings = resolved
    app.state.r2 = build_r2_storage(resolved)
    app.include_router(platform_router)
    app.include_router(media_router)
    _remove_legacy_login_start_route()
    app.include_router(shared_login_router)
    app.include_router(auth_router)
    app.include_router(account_settings_router)
    app.include_router(business_opening_router)
    app.include_router(profiles_router)
    app.include_router(business_online_router)
    app.include_router(public_discovery_router)
    app.include_router(catalog_router)
    app.include_router(advertisements_router)
    app.include_router(advertisement_authoring_router)
    app.include_router(listings_router)
    app.include_router(stories_router)
    app.include_router(specialists_router)
    app.include_router(messages_router)
    app.include_router(reviews_router)
    app.include_router(notifications_router)
    app.include_router(orders_router)
    app.include_router(taxi_router)
    app.include_router(follows_router)
    app.include_router(payments_router)
    app.include_router(admin_router)
    app.include_router(taxi_admin_router)
    app.include_router(reports_router)
    app.include_router(queues_router)
    app.include_router(education_router)
    app.include_router(staff_router)
    app.include_router(inventory_router)
    app.include_router(cash_register_router)
    app.include_router(debt_ledger_router)
    app.include_router(dining_router)
    app.include_router(documents_router)
    app.include_router(ai_assistant_router)
    app.include_router(expenses_router)
    app.include_router(statistics_router)

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
