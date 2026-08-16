"""Autentifikatsiya xizmati — mavzu bo'yicha mixin'lar.

base         -> kod yuborish, tekshiruv qoidalari
registration -> ro'yxatdan o'tish
login        -> kirish
sessions     -> seans (Redis keshi + baza)
"""

from app.auth.service_parts.service import AuthService

__all__ = ["AuthService"]
