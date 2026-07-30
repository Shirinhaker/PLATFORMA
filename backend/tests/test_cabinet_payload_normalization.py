from __future__ import annotations

import hashlib
import json

import pytest

from app.cabinet_records.codec import flatten_records, inflate_records
from app.cabinet_records.verify import payload_digest, verify_payload_parity


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_nested_cabinet_records_round_trip_without_json_blob() -> None:
    rows = [
        {
            "id": 44,
            "title": "Muhr",
            "status": "new",
            "total_amount": 15000,
            "paid": False,
            "note": None,
            "items": [
                {"id": 1, "name": "Non", "qty": 2, "price": 5000},
                {"id": 2, "name": "Choy", "qty": 1, "price": 5000},
            ],
            "messages": [
                {"id": 8, "text": "Assalomu alaykum", "sender_kind": "user"}
            ],
        }
    ]

    records, fields = flatten_records(
        account_id=7,
        account_type="business",
        resource="orders",
        rows=rows,
    )

    assert len(records) == 1
    assert records[0].resource == "orders"
    assert records[0].source_key == "44"
    assert records[0].payload_json is None
    assert fields
    assert all(field.value_json is None for field in fields)

    restored = inflate_records(records, fields)
    assert canonical(restored) == canonical(rows)
    assert payload_digest(restored) == payload_digest(rows)


def test_resource_and_account_boundaries_are_not_mixed() -> None:
    business_records, business_fields = flatten_records(
        account_id=7,
        account_type="business",
        resource="items",
        rows=[{"id": 1, "name": "Biznes mahsuloti"}],
    )
    user_records, user_fields = flatten_records(
        account_id=9,
        account_type="user",
        resource="listings",
        rows=[{"id": 1, "title": "Oddiy foydalanuvchi e’loni"}],
    )

    restored_business = inflate_records(business_records, business_fields)
    restored_user = inflate_records(user_records, user_fields)

    assert restored_business == [{"id": 1, "name": "Biznes mahsuloti"}]
    assert restored_user == [{"id": 1, "title": "Oddiy foydalanuvchi e’loni"}]
    assert business_records[0].account_id != user_records[0].account_id
    assert business_records[0].account_type != user_records[0].account_type
    assert business_records[0].resource != user_records[0].resource


def test_verify_requires_exact_count_and_digest_parity() -> None:
    source = {
        "orders": [{"id": 1, "status": "new"}],
        "items": [{"id": 2, "name": "Mahsulot"}],
    }
    target = {
        "orders": [{"id": 1, "status": "new"}],
        "items": [{"id": 2, "name": "Mahsulot"}],
    }

    result = verify_payload_parity(source, target)
    assert result.ok is True
    assert result.source_resources == 2
    assert result.target_resources == 2
    assert result.source_records == 2
    assert result.target_records == 2
    assert result.source_digest == result.target_digest

    broken = verify_payload_parity(
        source,
        {"orders": [{"id": 1, "status": "accepted"}]},
    )
    assert broken.ok is False
    assert broken.source_digest != broken.target_digest


def test_digest_is_stable_for_key_order_but_not_data_changes() -> None:
    first = [{"id": 1, "name": "Muhr", "price": 15000}]
    reordered = [{"price": 15000, "name": "Muhr", "id": 1}]
    changed = [{"id": 1, "name": "Muhr", "price": 16000}]

    assert payload_digest(first) == payload_digest(reordered)
    assert payload_digest(first) != payload_digest(changed)
    assert payload_digest(first) == hashlib.sha256(canonical(first).encode()).hexdigest()
