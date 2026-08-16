"""`AuthService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.auth.service_parts.base import AuthServiceBase
from app.auth.service_parts.login import LoginMixin
from app.auth.service_parts.registration import RegistrationMixin
from app.auth.service_parts.sessions import SessionsMixin


class AuthService(
    RegistrationMixin,
    LoginMixin,
    SessionsMixin,
    AuthServiceBase,
):
    """Ro'yxatdan o'tish, kirish va seans boshqaruvi."""
