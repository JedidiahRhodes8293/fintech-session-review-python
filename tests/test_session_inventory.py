from src.session_inventory import choose_sessions_to_revoke


def test_high_risk_review_keeps_current_device_and_selects_other_sessions():
    sessions = [
        {"session_id": "session-current", "device": "studio-browser"},
        {"session_id": "session-phone", "device": "phone"},
    ]

    assert choose_sessions_to_revoke(sessions, "session-current", 85) == ["session-phone"]
    assert choose_sessions_to_revoke(sessions, "session-current", 40) == []

