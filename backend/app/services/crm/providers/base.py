"""CRM provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CRMConnectionHealth:
    ok: bool
    provider: str
    external_id: str
    details: dict[str, Any]


class CRMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def validate_connection(self) -> CRMConnectionHealth:
        raise NotImplementedError

    @abstractmethod
    async def find_contact(self, *, query: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_contact(self, *, name: str, phone: str | None = None, email: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def find_lead(self, *, query: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_lead(self, *, name: str, price: int | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_lead(self, *, lead_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def add_note(self, *, entity_type: str, entity_id: int, text: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_task(
        self,
        *,
        text: str,
        complete_till_unix: int,
        entity_type: str,
        entity_id: int,
        responsible_user_id: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def assign_owner(self, *, entity_type: str, entity_id: int, responsible_user_id: int) -> dict[str, Any]:
        raise NotImplementedError
