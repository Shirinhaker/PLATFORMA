from __future__ import annotations

from copy import deepcopy
from typing import Mapping


def sync_json_fallback(profile, payload: Mapping[str, object]) -> None:
    """Temporary cutover safety; removed after verified JSON cleanup."""
    profile.cabinet_payload = deepcopy(dict(payload))
