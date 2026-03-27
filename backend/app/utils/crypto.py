import os

from cryptography.fernet import Fernet


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

