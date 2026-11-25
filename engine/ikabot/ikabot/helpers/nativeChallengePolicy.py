"""Human-controlled challenge stop policy for managed tasks."""
from ikabot.helpers import sessionStorage
from ikabot.helpers.botComm import _native_notification_destination, native_notification_ready
from ikabot.helpers.nativeNotificationSettings import _provider_accepts

_MODES = ("stop", "notify_and_stop")
_TEXT = "Daedalus: a game challenge requires human attention. Managed task stopped."


def status(session):
    data = session.getSessionData()
    mode = data.get("daedalusChallengePolicy", "stop")
    if mode not in _MODES:
        mode = "stop"
    return {"mode": mode, "notification_ready": any(
        native_notification_ready(session, p) for p in ("telegram", "discord"))}


def configure(session, draft):
    if (not isinstance(draft, dict) or set(draft) != {"mode", "expected_mode", "confirmed"}
            or draft["mode"] not in _MODES or draft["expected_mode"] not in _MODES
            or draft["confirmed"] is not True):
        raise ValueError("Invalid human challenge policy")
    with sessionStorage.session_data_lock():
        current = status(session)
        if current["mode"] != draft["expected_mode"]:
            raise ValueError("Human challenge policy changed")
        if draft["mode"] == "notify_and_stop" and not current["notification_ready"]:
            raise ValueError("Configure a supported notification destination first")
        data = dict(session.getSessionData())
        data.pop("shared", None)
        data["daedalusChallengePolicy"] = draft["mode"]
        session.setSessionData(data)
        return {"mode": draft["mode"], "notification_ready": current["notification_ready"]}


def stop_at_challenge(session):
    """Send at most one fixed notice; never retrieve, solve or submit a challenge."""
    session.setStatus("Human challenge required; managed task stopped")
    try:
        if status(session)["mode"] != "notify_and_stop":
            return
        for provider in ("telegram", "discord"):
            if not native_notification_ready(session, provider):
                continue
            url, body = _native_notification_destination(session, provider)
            key = "text" if provider == "telegram" else "content"
            _provider_accepts(provider, url, {**body, key: _TEXT})
            break
    except Exception:
        # No provider credentials or challenge content in logs or exceptions.
        return
