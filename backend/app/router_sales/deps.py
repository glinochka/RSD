from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..utils.JWT import decode_access_token_payload

http_bearer_sales = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SalesAuthContext:
    staff_id: int
    role: str


async def get_sales_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_sales),
) -> SalesAuthContext:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    payload = decode_access_token_payload(credentials.credentials, "sales_staff")
    sid = payload.get("sales_staff_id")
    role = payload.get("role")
    if not sid or role not in ("trainee", "mop", "rop"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен недействителен")
    return SalesAuthContext(staff_id=int(sid), role=str(role))


async def require_sales_rop(auth: SalesAuthContext = Depends(get_sales_auth)) -> SalesAuthContext:
    if auth.role != "rop":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для РОП")
    return auth
