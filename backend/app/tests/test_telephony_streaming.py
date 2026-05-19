from __future__ import annotations

from app.telephony.streaming import extract_complete_sentences, split_sentences


def test_split_sentences_russian():
    text = "Добрый день. Чем помочь? Запишу вас на завтра!"
    parts = split_sentences(text)
    assert len(parts) == 3
    assert parts[0].startswith("Добрый")


def test_extract_complete_sentences_buffers_tail():
    complete, tail = extract_complete_sentences("Первая фраза. Вторая без")
    assert complete == ["Первая фраза."]
    assert "Вторая" in tail
