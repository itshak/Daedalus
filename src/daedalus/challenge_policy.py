"""Human attention only; no challenge answer or solver credential fields."""
MODES = ("stop", "notify_and_stop")


def validate_challenge_policy(value, account):
    if (not isinstance(value, dict) or set(value) != {"account_id", "mode", "notification_ready"}
            or value["account_id"] != account or value["mode"] not in MODES
            or type(value["notification_ready"]) is not bool):
        raise ValueError("Invalid human challenge policy")
    return value


def validate_challenge_policy_draft(value):
    if (not isinstance(value, dict) or set(value) != {"mode", "expected_mode", "confirmed"}
            or value["mode"] not in MODES or value["expected_mode"] not in MODES
            or value["confirmed"] is not True):
        raise ValueError("Invalid human challenge policy")
    return value
