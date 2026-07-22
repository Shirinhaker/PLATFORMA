"""Platformadagi maxsus profil huquqlari."""

import os


def _privileged_ids():
    raw = os.environ.get("PRIVILEGED_TG_IDS", "1423181561,607563067")
    result = set()
    for value in raw.split(","):
        try:
            result.add(int(value.strip()))
        except (TypeError, ValueError):
            pass
    return result


PRIVILEGED_TG_IDS = _privileged_ids()


def is_privileged_tg_id(tg_id):
    try:
        return int(tg_id) in PRIVILEGED_TG_IDS
    except (TypeError, ValueError):
        return False
