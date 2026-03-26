from datetime import datetime, timezone
from logging import getLogger

from sqlalchemy import update

from ..alembic.database import async_session_maker
from ..alembic.models import User

logger = getLogger(__name__)


async def downgrade_expired_subscriptions_once() -> int:
    """
    Downgrade expired paid users to Free plan.
    Returns number of updated rows.
    """
    now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session_maker() as session:
        async with session.begin():
            result = await session.execute(
                update(User)
                .where(User.subscription_type != "Free")
                .where(User.subscription_end_date.is_not(None))
                .where(User.subscription_end_date < now_naive_utc)
                .values(subscription_type="Free", subscription_end_date=None)
            )
            updated_count = int(result.rowcount or 0)

    if updated_count:
        logger.info("Auto-downgraded %s expired subscriptions to Free", updated_count)
    return updated_count

