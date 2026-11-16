import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from config import get_db_url

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, declared_attr



DATABASE_URL = get_db_url()
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def release_session_before_wait(session: AsyncSession) -> None:
    """Finish the current transaction and give the connection back to the pool.

    The next await (LLM, Telegram) must not leave this connection idle in a
    transaction. Pending writes are committed; a read-only transaction is
    committed too, which only ends it. expire_on_commit is off, so loaded
    objects stay usable. A nested savepoint is left to its owner.
    """
    if session.in_nested_transaction() or not session.in_transaction():
        return
    try:
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        raise


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"
   