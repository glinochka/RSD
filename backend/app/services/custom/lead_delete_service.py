"""Delete custom leads (admin / lab retest)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomLead, CustomLeadMessage


async def delete_lead(
    session: AsyncSession,
    automation_id: int,
    lead_id: int,
) -> bool:
    lead = await session.scalar(
        select(CustomLead).where(
            CustomLead.id == lead_id,
            CustomLead.custom_automation_id == automation_id,
        )
    )
    if lead is None:
        return False
    messages = (
        await session.execute(
            select(CustomLeadMessage).where(CustomLeadMessage.custom_lead_id == lead.id)
        )
    ).scalars().all()
    for message in messages:
        await session.delete(message)
    await session.delete(lead)
    await session.commit()
    return True
