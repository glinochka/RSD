from app.services.agent_autopay import extract_saved_payment_method_id


def test_extract_saved_payment_method_id_from_dict():
    payment = {
        "payment_method": {
            "id": "pm-123",
            "saved": True,
            "type": "bank_card",
        }
    }
    assert extract_saved_payment_method_id(payment) == "pm-123"


def test_extract_saved_payment_method_id_not_saved():
    payment = {"payment_method": {"id": "pm-123", "saved": False}}
    assert extract_saved_payment_method_id(payment) is None


class _Pm:
    def __init__(self, pm_id: str, saved: bool):
        self.id = pm_id
        self.saved = saved


class _Payment:
    def __init__(self, pm_id: str, saved: bool):
        self.payment_method = _Pm(pm_id, saved)


def test_extract_saved_payment_method_id_from_object():
    assert extract_saved_payment_method_id(_Payment("pm-obj", True)) == "pm-obj"
