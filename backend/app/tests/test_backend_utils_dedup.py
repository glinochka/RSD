"""Unit tests for shared backend utils (refactor phase 1)."""

import json
from datetime import datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.utils.agent_template_config import parse_agent_template_config
from app.utils.scoped_auth_token import ScopedAuthToken, userbot_auth_token
from app.utils.whatsapp_jid import (
    WhatsAppJidError,
    external_id_to_jid,
    is_private_whatsapp_jid,
    jid_for_whatsapp_analytics,
    normalize_whatsapp_external_id,
)


class TestParseAgentTemplateConfig:
    def test_none_returns_empty_dict(self):
        assert parse_agent_template_config(None) == {}

    def test_none_if_empty_returns_none(self):
        assert parse_agent_template_config(None, none_if_empty=True) is None

    def test_invalid_json_returns_empty(self):
        assert parse_agent_template_config("{not json") == {}

    def test_non_dict_json_returns_empty(self):
        assert parse_agent_template_config("[1, 2]") == {}

    def test_dict_input_passthrough(self):
        assert parse_agent_template_config({"a": 1}) == {"a": 1}

    def test_json_string(self):
        assert parse_agent_template_config('{"k": "v"}') == {"k": "v"}


class TestWhatsAppJid:
    def test_normalize_digits_to_jid(self):
        assert normalize_whatsapp_external_id("6281234567890") == "6281234567890@s.whatsapp.net"

    def test_normalize_existing_jid_lowercase(self):
        assert normalize_whatsapp_external_id("6281234567890@S.whatsapp.net") == "6281234567890@s.whatsapp.net"

    def test_external_id_to_jid_from_digits(self):
        assert external_id_to_jid("79001234567") == "79001234567@s.whatsapp.net"

    def test_external_id_to_jid_passthrough(self):
        assert external_id_to_jid("79001234567@s.whatsapp.net") == "79001234567@s.whatsapp.net"

    def test_external_id_to_jid_empty_raises(self):
        with pytest.raises(WhatsAppJidError):
            external_id_to_jid("")

    def test_external_id_to_jid_short_digits_raises(self):
        with pytest.raises(WhatsAppJidError):
            external_id_to_jid("1234")

    def test_jid_for_analytics_truncates(self):
        long_jid = "x" * 200 + "@s.whatsapp.net"
        assert len(jid_for_whatsapp_analytics(long_jid)) == 128

    def test_is_private_whatsapp_jid(self):
        assert is_private_whatsapp_jid("79001234567@s.whatsapp.net") is True
        assert is_private_whatsapp_jid("79001234567@lid") is True
        assert is_private_whatsapp_jid("123@g.us") is False


class TestScopedAuthToken:
    def test_create_and_decode(self):
        token = userbot_auth_token.create(api_id=1, phone_number="+1")
        data = userbot_auth_token.decode(token)
        assert data["scope"] == "userbot_auth"
        assert data["api_id"] == 1

    def test_scope_mismatch_raises(self):
        other = ScopedAuthToken(
            "other_scope",
            invalid_detail="bad",
            scope_mismatch_detail="wrong scope",
        )
        token = other.create(x=1)
        with pytest.raises(HTTPException) as exc:
            userbot_auth_token.decode(token)
        assert exc.value.status_code == 401

    def test_expired_token_raises(self):
        expired = ScopedAuthToken(
            "exp_test",
            ttl_minutes=-1,
            invalid_detail="expired",
            scope_mismatch_detail="wrong",
        )
        now = datetime.utcnow()
        payload = {
            "scope": "exp_test",
            "exp": now - timedelta(minutes=1),
            "iat": now - timedelta(minutes=2),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            expired.decode(token)
        assert exc.value.status_code == 401

    def test_required_keys(self):
        token = userbot_auth_token.create(api_id=1)
        with pytest.raises(HTTPException):
            userbot_auth_token.decode(token, required_keys=["missing_key"])
