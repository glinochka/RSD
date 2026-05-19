"""IVR / compliance copy for telephony pilot."""

from __future__ import annotations

RECORDING_DISCLAIMER_RU = (
    "Здравствуйте. Ваш разговор может быть записан для контроля качества и обучения сервиса. "
    "Продолжая разговор, вы соглашаетесь на обработку персональных данных в соответствии "
    "с политикой конфиденциальности компании. Если вы не согласны — положите трубку "
    "или нажмите ноль для связи с оператором."
)

RECORDING_DISCLAIMER_SHORT_RU = (
    "Разговор может быть записан. Продолжая, вы соглашаетесь с политикой конфиденциальности "
    "на сайте компании."
)


def recording_disclaimer_text(*, short: bool = False) -> str:
    return RECORDING_DISCLAIMER_SHORT_RU if short else RECORDING_DISCLAIMER_RU
