from app.telephony.masking import mask_caller_e164


def test_mask_caller_e164():
    assert mask_caller_e164("+79001234567") == "+7900***4567"
    assert mask_caller_e164("") == "***"
