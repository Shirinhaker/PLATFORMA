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
from app.cabinet_records.model import CabinetRecord, CabinetRecordField


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
        record_id = await session.scalar(
            select(CabinetRecord.id)
            .where(
                CabinetRecord.account_id == account_id,
                CabinetRecord.account_type == account_type,
                CabinetRecord.resource == resource,
            )
            .limit(1)
        )
        return record_id is not None

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
        records = list(
            (
                await session.scalars(
                    select(CabinetRecord)
                    .where(
                        CabinetRecord.account_id == account_id,
                        CabinetRecord.account_type == account_type,
                        CabinetRecord.resource == resource,
                    )
                    .order_by(CabinetRecord.ordinal, CabinetRecord.id)
                )
            ).all()
        )
        if not records:
            return []
        record_ids = [record.id for record in records]
        fields = list(
            (
                await session.scalars(
                    select(CabinetRecordField)
                    .where(CabinetRecordField.record_id.in_(record_ids))
                    .order_by(CabinetRecordField.record_id, CabinetRecordField.path)
                )
            ).all()
        )
        source_by_id = {record.id: record.source_key for record in records}
        flat_records = [
            FlatRecord(
                account_id=record.account_id,
                account_type=record.account_type,
                resource=record.resource,
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
        ]
        return inflate_records(flat_records, flat_fields)

    async def read_payload(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> dict[str, list[dict[str, Any]]]:
        if not hasattr(session, "scalars"):
            return {}
        resources = list(
            (
                await session.scalars(
                    select(CabinetRecord.resource)
                    .where(
                        CabinetRecord.account_id == account_id,
                        CabinetRecord.account_type == account_type,
                    )
                    .distinct()
                    .order_by(CabinetRecord.resource)
                )
            ).all()
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for resource in resources:
            result[resource] = await self.read_resource(
                session,
                account_id=account_id,
                account_type=account_type,
                resource=resource,
            )
        return result

    async def replace_resource(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        resource: str,
        rows: list[dict[str, Any]],
    ) -> None:
        await session.execute(
            delete(CabinetRecord).where(
                CabinetRecord.account_id == account_id,
                CabinetRecord.account_type == account_type,
                CabinetRecord.resource == resource,
            )
        )
        await session.flush()
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
                account_id=flat_record.account_id,
                account_type=flat_record.account_type,
                resource=flat_record.resource,
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

    async def replace_payload(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        payload: Mapping[str, object],
    ) -> None:
        await session.execute(
            delete(CabinetRecord).where(
                CabinetRecord.account_id == account_id,
                CabinetRecord.account_type == account_type,
            )
        )
        await session.flush()
        for resource, value in sorted(payload.items()):
            rows = normalize_payload_rows(value)
            if not rows:
                continue
            await self.replace_resource(
                session,
                account_id=account_id,
                account_type=account_type,
                resource=str(resource),
                rows=rows,
            )
