from passlib.context import CryptContext
from passlib.exc import UnknownHashError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError as exc:
        # Malformed bcrypt strings (e.g. plain password in ADMIN_WEB_PASSWORD_HASH)
        # raise ValueError inside passlib, not UnknownHashError.
        raise UnknownHashError("invalid bcrypt hash format") from exc
