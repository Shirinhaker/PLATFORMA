from app.core.errors import ApiError


def validate_status_change(*, current: str, requested: str, side: str) -> None:
    if requested in {"accepted", "rejected"} and side != "provider":
        raise ApiError(
            403,
            "order_status_provider_required",
            "Bu buyurtma holatini faqat qabul qiluvchi kabinet o'zgartira oladi.",
        )
    if requested == "tayyor":
        if side != "provider":
            raise ApiError(
                403,
                "order_status_provider_required",
                "Bu buyurtma holatini faqat qabul qiluvchi kabinet o'zgartira oladi.",
            )
        if current != "preparing":
            raise ApiError(
                409,
                "order_not_preparing",
                "Buyurtma faqat Tayyorlanmoqda holatidan tayyor qilinadi.",
            )
        return
    allowed = {
        ("provider", "new", "accepted"),
        ("provider", "new", "rejected"),
        ("provider", "new", "cancelled"),
        ("provider", "accepted", "cancelled"),
        ("customer", "new", "cancelled"),
        ("customer", "accepted", "cancelled"),
    }
    if (side, current, requested) not in allowed:
        raise ApiError(
            409,
            "order_status_transition_invalid",
            "Buyurtma holatini bunday o'zgartirib bo'lmaydi.",
        )
