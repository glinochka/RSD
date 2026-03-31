from ..alembic.models import TelegramLinkChallenge, User
from ..BaseDAO import BaseDAO


class UserDAO(BaseDAO):
    model = User

class TelegramLinkChallengeDAO(BaseDAO):
    model = TelegramLinkChallenge