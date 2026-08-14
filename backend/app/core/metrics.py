from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS = Counter(
    "koprik_http_requests_total",
    "HTTP so'rovlar soni",
    ("method", "route", "status"),
)
HTTP_LATENCY = Histogram(
    "koprik_http_request_duration_seconds",
    "HTTP so'rov davomiyligi",
    ("method", "route"),
)
EXTERNAL_ERRORS = Counter(
    "koprik_external_errors_total",
    "Tashqi servis xatolari",
    ("provider",),
)
DB_POOL_SIZE = Gauge("koprik_db_pool_size", "DB pool o'lchami")
DB_POOL_CHECKED_OUT = Gauge(
    "koprik_db_pool_checked_out",
    "Band DB connectionlar",
)
DB_POOL_OVERFLOW = Gauge("koprik_db_pool_overflow", "DB pool overflow")
OUTBOX_PENDING = Gauge("koprik_outbox_pending", "Kutilayotgan outbox eventlar")
OUTBOX_OLDEST_AGE = Gauge(
    "koprik_outbox_oldest_age_seconds",
    "Eng eski outbox event yoshi",
)


def update_db_pool_metrics(database) -> None:
    engine = getattr(database, "engine", None)
    pool = getattr(engine, "pool", None)
    if pool is None:
        return
    for gauge, method in (
        (DB_POOL_SIZE, "size"),
        (DB_POOL_CHECKED_OUT, "checkedout"),
        (DB_POOL_OVERFLOW, "overflow"),
    ):
        value = getattr(pool, method, None)
        if callable(value):
            gauge.set(max(0, value()))
