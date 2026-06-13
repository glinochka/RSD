from app.services.sales.fsm import SalesFSMService


def test_sales_fsm_allowed_transitions():
    svc = SalesFSMService()
    assert svc._can_transition("DISCOVERED", "QUALIFIED") is True
    assert svc._can_transition("QUALIFIED", "QUEUED") is True
    assert svc._can_transition("QUEUED", "SENT") is True
    assert svc._can_transition("SENT", "REPLIED_POSITIVE") is True
    assert svc._can_transition("REPLIED_POSITIVE", "HANDOFF_CRM") is True


def test_sales_fsm_denied_transitions():
    svc = SalesFSMService()
    assert svc._can_transition("DISCOVERED", "SENT") is False
    assert svc._can_transition("SKIPPED", "QUEUED") is False
    assert svc._can_transition("NO_REPLY", "HANDOFF_CRM") is False
