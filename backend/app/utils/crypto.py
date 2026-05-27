import os

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from ..config import settings


def _get_cipher_suite() -> Fernet:
  """
  Must use the same ENCRYPTION_KEY as `bot/core/crypto.py`,
  otherwise `bot` will be unable to decrypt `encrypted_token`.
  """
  secret_key = os.getenv("ENCRYPTION_KEY")
  if not secret_key:
    raise RuntimeError(
      'ENCRYPTION_KEY is not set for backend. Set it to the same value as in docker-compose for the bot.'
    )

  return Fernet(secret_key.encode())


def _get_crm_primary_key() -> str:
  key = settings.CRM_CREDENTIALS_ENCRYPTION_KEY.strip() or os.getenv("ENCRYPTION_KEY", "").strip()
  if not key:
    raise RuntimeError("CRM_CREDENTIALS_ENCRYPTION_KEY is not configured")
  return key


def _get_crm_legacy_key() -> str:
  return settings.CRM_CREDENTIALS_ENCRYPTION_KEY_PREVIOUS.strip() or ""


def encrypt_token(token: str) -> str:
  cipher_suite = _get_cipher_suite()
  return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
  """
  Decrypts encrypted Telegram token stored in DB.
  Must use the same ENCRYPTION_KEY as `bot/core/crypto.py`.
  """
  cipher_suite = _get_cipher_suite()
  return cipher_suite.decrypt(encrypted_token.encode()).decode()


def encrypt_crm_credentials(payload: str) -> str:
  cipher = Fernet(_get_crm_primary_key().encode())
  return f"crmv1:{cipher.encrypt(payload.encode()).decode()}"


def decrypt_crm_credentials(encrypted_payload: str) -> tuple[str, bool]:
  """
  Returns: (decrypted_payload, needs_rotation).
  """
  value = (encrypted_payload or "").strip()
  if not value:
    raise RuntimeError("Empty CRM encrypted payload")

  if value.startswith("crmv1:"):
    token = value.split(":", 1)[1]
    cipher = Fernet(_get_crm_primary_key().encode())
    return cipher.decrypt(token.encode()).decode(), False

  primary = Fernet(_get_crm_primary_key().encode())
  try:
    return primary.decrypt(value.encode()).decode(), True
  except InvalidToken:
    legacy = _get_crm_legacy_key()
    if not legacy:
      raise
    fallback = Fernet(legacy.encode())
    return fallback.decrypt(value.encode()).decode(), True


def _get_booking_primary_key() -> str:
  key = settings.BOOKING_PAYMENT_ENCRYPTION_KEY.strip() or settings.CRM_CREDENTIALS_ENCRYPTION_KEY.strip() or os.getenv("ENCRYPTION_KEY", "").strip()
  if not key:
    raise RuntimeError("BOOKING_PAYMENT_ENCRYPTION_KEY is not configured")
  return key


def encrypt_booking_payment_secret(secret: str) -> str:
  cipher = Fernet(_get_booking_primary_key().encode())
  return f"bpay1:{cipher.encrypt(secret.encode()).decode()}"


def decrypt_booking_payment_secret(encrypted_payload: str) -> str:
  value = (encrypted_payload or "").strip()
  if not value:
    raise RuntimeError("Empty booking payment encrypted payload")
  if value.startswith("bpay1:"):
    token = value.split(":", 1)[1]
    cipher = Fernet(_get_booking_primary_key().encode())
    return cipher.decrypt(token.encode()).decode()
  cipher = Fernet(_get_booking_primary_key().encode())
  return cipher.decrypt(value.encode()).decode()

