from app.telephony.intent import detect_hangup_intent, detect_operator_transfer_intent


def test_detect_hangup_intent():
    assert detect_hangup_intent("Спасибо, до свидания!")
    assert not detect_hangup_intent("Хочу записаться на завтра")


def test_detect_operator_transfer_intent():
    assert detect_operator_transfer_intent("Соедините с человеком, пожалуйста")
    assert not detect_operator_transfer_intent("Сколько стоит доставка?")
