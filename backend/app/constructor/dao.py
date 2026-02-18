
from ..alembic.models import User
from ..BaseDAO import BaseDAO


class UserDAO(BaseDAO):
    model = User