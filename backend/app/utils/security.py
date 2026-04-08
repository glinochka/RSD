from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def identify_password_hash_scheme(hashed_password: str | None) -> str | None:
    if not hashed_password:
        return None
    try:
        return pwd_context.identify(hashed_password)
    except (TypeError, ValueError):
        return None
