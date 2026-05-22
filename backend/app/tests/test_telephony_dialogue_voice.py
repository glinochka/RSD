from app.channels.telephony_dialogue import (
    MSG_CRM_FILLER,
    MSG_RAG_FILLER,
    _filler_for_turn,
    _prepend_opening_ack,
)


def test_filler_for_turn_rag():
    text, play = _filler_for_turn(used_rag=True, crm_slow=False)
    assert play is True
    assert text == MSG_RAG_FILLER


def test_filler_for_turn_crm_priority():
    text, play = _filler_for_turn(used_rag=True, crm_slow=True)
    assert play is True
    assert text == MSG_CRM_FILLER


def test_prepend_opening_ack():
    chunks = _prepend_opening_ack(["Запись возможна завтра."], call_id=3)
    assert chunks[0].startswith("Понял.")
    assert "Запись возможна" in chunks[0]
