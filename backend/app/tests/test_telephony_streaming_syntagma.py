from __future__ import annotations

from app.telephony.streaming import extract_complete_syntagmas, split_syntagmas


def test_split_syntagmas_commas():
    parts = split_syntagmas("Добрый день, чем помочь? Запишу вас.", min_chars=5)
    assert len(parts) >= 2
    assert any("Добрый" in p for p in parts)


def test_extract_complete_syntagmas_tail():
    complete, tail = extract_complete_syntagmas("Первая фраза, вторая без", min_chars=5)
    assert complete
    assert "вторая" in tail
