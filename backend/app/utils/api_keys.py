import hashlib
import secrets


def generate_agent_external_api_key() -> str:
    # Prefix makes keys easier to identify in logs/UI.
    return f"agnt_{secrets.token_urlsafe(32)}"


def hash_agent_external_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
