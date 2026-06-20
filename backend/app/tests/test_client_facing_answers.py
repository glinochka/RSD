from app.prompts.system_prompts import (
    CLIENT_OPERATOR_ESCALATION_MESSAGE,
    coerce_client_facing_answer,
    looks_like_internal_meta_answer,
)
from app.services.template_runtime import TemplateRuntimeService


def test_looks_like_internal_meta_answer_detects_operator_leak() -> None:
    text = (
        "Клиент запрашивает информацию о предоставлении, "
        "что требует доступа к внутренним системным данным, недоступно мне."
    )
    assert looks_like_internal_meta_answer(text) is True


def test_coerce_client_facing_answer_replaces_meta() -> None:
    meta = "Клиент запрашивает X, требуется помощь оператора для предоставления информации."
    assert coerce_client_facing_answer(meta) == CLIENT_OPERATOR_ESCALATION_MESSAGE


def test_extract_owner_handoff_keeps_client_part_before_marker() -> None:
    answer, handoff, reason, escalation = TemplateRuntimeService._extract_owner_handoff(
        "Хорошо, сейчас уточню у коллеги.\n[OPERATOR_ASSIST] Нужны внутренние данные по тарифу."
    )
    assert handoff is True
    assert "уточню у коллеги" in answer
    assert "внутренние данные" not in answer
    assert reason is not None
    assert escalation.value == "notify_only"
