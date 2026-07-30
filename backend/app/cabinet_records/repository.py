from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cabinet_records.codec import (
    FlatField,
    FlatRecord,
    flatten_records,
    inflate_records,
    normalize_payload_rows,
)
from app.cabinet_records.model import (
    CabinetRecord,
    CabinetRecordField,
    CabinetResource,
)
from app.cabinet_records.verify import payload_digest


class CabinetRecordRepository:
    async def has_resource(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        resource: str,
    ) -> bool:
        if not hasattr(session, "scalar"):
            return False
        resource_id = await session.scalar(
            select(CabinetResource.id)
            .where(
                CabinetResource.account_id == account_id,
                CabinetResource.account_type == account_type,
                CabinetResource.resource == resource,
            )
            .limit(1)
        )
        return resource_id is not None

    async def read_resource(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        resource: str,
    ) -> list[dict[str, Any]]:
        if not hasattr(session, "scalars"):
            return []
        marker = await session.scalar(
            select(CabinetResource).where(
                CabinetResource.account_id == account_id,
                CabinetResource.account_type == account_type,
                CabinetResource.resource == resource,
            )
        )
        if marker is None:
            return []
        records = list(
            (
                await session.scalars(
                    select(CabinetRecord)
                    .where(CabinetRecord.resource_id == marker.id)
                    .order_by(CabinetRecord.ordinal, CabinetRecord.id)
                )
            ).all()
        )
        fields = await self._fields_for_records(session, records)
        return _inflate_rows(marker, records, fields)

    async def read_payload(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> dict[str, Any]:
        if not hasattr(session, "scalars"):
            return {}
        resources = list(
            (
                await session.scalars(
                    select(CabinetResource)
                    .where(
                        CabinetResource.account_id == account_id,
                        CabinetResource.account_type == account_type,
                    )
                    .order_by(CabinetResource.resource)
                )
            ).all()
        )
        if not resources:
            return {}
        resource_ids = [resource.id for resource in resources]
        records = list(
            (
                await session.scalars(
                    select(CabinetRecord)
                    .where(CabinetRecord.resource_id.in_(resource_ids))
                    .order_by(
                        CabinetRecord.resource_id,
                        CabinetRecord.ordinal,
                        CabinetRecord.id,
                    )
                )
            ).all()
        )
        fields = await self._fields_for_records(session, records)
        records_by_resource: dict[int, list[CabinetRecord]] = defaultdict(list)
        for record in records:
            records_by_resource[record.resource_id].append(record)

        result: dict[str, Any] = {}
        for marker in resources:
            rows = _inflate_rows(
                marker,
                records_by_resource.get(marker.id, []),
                fields,
            )
            result[marker.resource] = restore_resource_value(marker.value_kind, rows)
        return result

    async def replace_resource(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        resource: str,
        rows: list[dict[str, Any]],
        value_kind: str = "list",
    ) -> None:
        marker = await session.scalar(
            select(CabinetResource)
            .where(
                CabinetResource.account_id == account_id,
                CabinetResource.account_type == account_type,
                CabinetResource.resource == resource,
            )
            .with_for_update()
        )
        restored = restore_resource_value(value_kind, rows)
        if marker is None:
            marker = CabinetResource(
                account_id=account_id,
                account_type=account_type,
                resource=resource,
                value_kind=value_kind,
                record_count=len(rows),
                digest=payload_digest(restored),
            )
            session.add(marker)
            await session.flush()
        else:
            marker.value_kind = value_kind
            marker.record_count = len(rows)
            marker.digest = payload_digest(restored)
            await session.execute(
                delete(CabinetRecord).where(
                    CabinetRecord.resource_id == marker.id
                )
            )
            await session.flush()

        await self._insert_rows(
            session,
            marker=marker,
            account_id=account_id,
            account_type=account_type,
            resource=resource,
            rows=rows,
        )

    async def replace_payload(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        payload: Mapping[str, object],
    ) -> None:
        await session.execute(
            delete(CabinetResource).where(
                CabinetResource.account_id == account_id,
                CabinetResource.account_type == account_type,
            )
        )
        await session.flush()
        for resource, value in sorted(payload.items()):
            await self.replace_resource(
                session,
                account_id=account_id,
                account_type=account_type,
                resource=str(resource),
                rows=normalize_payload_rows(value),
                value_kind=resource_value_kind(value),
            )

    async def _fields_for_records(
        self,
        session: AsyncSession,
        records: list[CabinetRecord],
    ) -> list[CabinetRecordField]:
        if not records:
            return []
        record_ids = [record.id for record in records]
        return list(
            (
                await session.scalars(
                    select(CabinetRecordField)
                    .where(CabinetRecordField.record_id.in_(record_ids))
                    .order_by(CabinetRecordField.record_id, CabinetRecordField.path)
                )
            ).all()
        )

    async def _insert_rows(
        self,
        session: AsyncSession,
        *,
        marker: CabinetResource,
        account_id: int,
        account_type: str,
        resource: str,
        rows: list[dict[str, Any]],
    ) -> None:
        flat_records, flat_fields = flatten_records(
            account_id=account_id,
            account_type=account_type,
            resource=resource,
            rows=rows,
        )
        fields_by_key: dict[str, list[FlatField]] = defaultdict(list)
        for field in flat_fields:
            fields_by_key[field.record_source_key].append(field)

        for flat_record in flat_records:
            record = CabinetRecord(
                resource_id=marker.id,
                source_key=flat_record.source_key,
                ordinal=flat_record.ordinal,
            )
            session.add(record)
            await session.flush()
            for flat_field in fields_by_key.get(flat_record.source_key, []):
                session.add(
                    CabinetRecordField(
                        record_id=record.id,
                        path=flat_field.path,
                        value_type=flat_field.value_type,
                        value_text=flat_field.value_text,
                        value_integer=flat_field.value_integer,
                        value_float=flat_field.value_float,
                        value_boolean=flat_field.value_boolean,
                    )
                )
        await session.flush()


def resource_value_kind(value: object) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return "scalar"


def restore_resource_value(
    value_kind: str,
    rows: list[dict[str, Any]],
) -> object:
    if value_kind == "object":
        return rows[0] if rows else {}
    if value_kind == "null":
        return None
    if value_kind == "scalar":
        return rows[0].get("value") if rows else None
    return rows


def _inflate_rows(
    marker: CabinetResource,
    records: list[CabinetRecord],
    fields: list[CabinetRecordField],
) -> list[dict[str, Any]]:
    if not records:
        return []
    record_ids = {record.id for record in records}
    source_by_id = {record.id: record.source_key for record in records}
    flat_records = [
        FlatRecord(
            account_id=marker.account_id,
            account_type=marker.account_type,
            resource=marker.resource,
            source_key=record.source_key,
            ordinal=record.ordinal,
        )
        for record in records
    ]
    flat_fields = [
        FlatField(
            record_source_key=source_by_id[field.record_id],
            path=field.path,
            value_type=field.value_type,
            value_text=field.value_text,
            value_integer=field.value_integer,
            value_float=field.value_float,
            value_boolean=field.value_boolean,
        )
        for field in fields
        if field.record_id in record_ids
    ]
    return inflate_records(flat_records, flat_fields)
