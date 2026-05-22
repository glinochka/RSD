from app.router_agents.telephony_preview import strip_ssml_for_browser


def test_strip_ssml_for_browser():
    assert strip_ssml_for_browser("Привет") == "Привет"
    raw = '<speak><prosody rate="95%">Здравствуйте</prosody></speak>'
    assert strip_ssml_for_browser(raw) == "Здравствуйте"
