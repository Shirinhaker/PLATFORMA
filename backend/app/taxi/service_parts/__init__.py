"""Taksi xizmati — mavzu bo'yicha mixin'lar.

base     -> haydovchi/safar yuklash, masofa hisobi
drivers  -> haydovchilar
rides    -> safarlar
delivery -> yetkazib berish (buyurtma zanjiri)
"""

from app.taxi.service_parts.service import TaxiService

__all__ = ["TaxiService"]
