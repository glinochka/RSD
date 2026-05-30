from app.services.template_runtime import TemplateRuntimeService


def test_sanitize_preserves_payment_url_value():
    raw = "Оплатите по ссылке payment_url: https://yookassa.ru/checkout/abc"
    out = TemplateRuntimeService._sanitize_final_answer(raw)
    assert "https://yookassa.ru/checkout/abc" in out
    assert "технические данные скрыты" not in out


def test_sanitize_preserves_bare_https_url():
    raw = "Оплатите: https://yookassa.ru/checkout/abc"
    out = TemplateRuntimeService._sanitize_final_answer(raw)
    assert "https://yookassa.ru/checkout/abc" in out
    assert "технические данные скрыты" not in out


def test_sanitize_still_redacts_internal_json_keys():
    raw = "staff_id: 23, service_id: 5"
    out = TemplateRuntimeService._sanitize_final_answer(raw)
    assert "staff_id" not in out
    assert "технические данные скрыты" in out


def test_ensure_booking_payment_url_appends_when_missing():
    out = TemplateRuntimeService._ensure_booking_payment_url(
        "Нужна предоплата.",
        "https://yookassa.ru/pay/1",
    )
    assert "https://yookassa.ru/pay/1" in out


def test_ensure_booking_payment_url_replaces_redacted_placeholder():
    out = TemplateRuntimeService._ensure_booking_payment_url(
        "Вот ссылка для оплаты: технические данные скрыты Сумма — 50 000 руб.",
        "https://yookassa.ru/pay/1",
    )
    assert "https://yookassa.ru/pay/1" in out
    assert "технические данные скрыты" not in out


def test_ensure_booking_payment_url_survives_final_sanitize():
    raw_answer = "Запись создана. Вот ссылка для оплаты: технические данные скрыты"
    with_url = TemplateRuntimeService._ensure_booking_payment_url(
        raw_answer,
        "https://yookassa.ru/pay/1",
    )
    out = TemplateRuntimeService._sanitize_final_answer(with_url)
    assert "https://yookassa.ru/pay/1" in out
    assert "технические данные скрыты" not in out
