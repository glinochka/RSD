from .alembic.database import async_session_maker
from .alembic.models import Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



def require_transaction(func):
    async def wrapper(self, *args, **kwargs):
        if not self._session.in_transaction():
            raise RuntimeError("Session is not initialized")
        
        return await func(self, *args, **kwargs)
    return wrapper

class BaseDAO:
    model: Base = None

    def __init__(self, session: AsyncSession):
        self._session = session

    @require_transaction 
    async def find_one_by_filter(self, **filters) -> Base:
        comm = select(self.model).filter_by(**filters)
        one = await self._session.scalar(comm)
        return one
     
    @require_transaction
    async def delete(self, ob: Base) -> None:
        await self._session.delete(ob)

    @require_transaction
    async def add(self, element: dict) -> Base:
        new_element = self.model(**element)
        self._session.add(new_element)

        return new_element
    
    def update(self, ob: Base, updates: dict) -> None:

        for key, value in updates.items():
            if hasattr(ob, key):
                setattr(ob, key, value)

        