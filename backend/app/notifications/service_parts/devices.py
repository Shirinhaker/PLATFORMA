"""Push qurilmalari."""

from __future__ import annotations

from app.accounts.model import AccountType
from app.notifications.schemas import (
    NotificationMutationRead,
    PushDeviceRead,
    PushDeviceRemove,
    PushDeviceWrite,
    PushStatusRead,
)
from app.notifications.service_parts.base import NotificationServiceBase


class DevicesMixin(NotificationServiceBase):
    async def register_device(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PushDeviceWrite,
    ) -> PushDeviceRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            device_id = await self._repository.register_device(
                session,
                account_id=owner_id,
                token=body.token,
                platform=body.platform,
                device_name=body.device_name,
                app_version=body.app_version,
                now=self._now(),
            )
            await session.commit()
            return PushDeviceRead(device_id=device_id)

    async def unregister_device(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PushDeviceRemove,
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            await self._repository.unregister_device(
                session,
                account_id=owner_id,
                token=body.token,
                now=self._now(),
            )
            await session.commit()
            return NotificationMutationRead()

    async def push_status(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> PushStatusRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            active, pending = await self._repository.push_status(
                session, account_id=owner_id
            )
            return PushStatusRead(
                configured=self._push_configured,
                active_devices=active,
                pending=pending,
            )
