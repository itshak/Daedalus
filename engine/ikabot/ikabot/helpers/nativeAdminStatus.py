"""Read-only projection of settings; never return stored credential values."""
from urllib.parse import urlsplit


def administrative_status(session):
    data = session.getSessionData()
    if not isinstance(data, dict):
        raise ValueError("Administrative settings unavailable")
    shared = data.get("shared")
    shared = shared if isinstance(shared, dict) else {}
    telegram = shared.get("telegram")
    discord = shared.get("discord")
    from ikabot.helpers.botComm import native_notification_ready

    proxy = data.get("proxy")
    proxy = proxy if isinstance(proxy, dict) else {}
    active = proxy.get("set") is True
    protocol = None
    port = None
    auth = None
    if active:
        conf = proxy.get("conf")
        value = conf.get("https") if isinstance(conf, dict) else None
        try:
            if isinstance(value, str):
                parsed = urlsplit(value)
                if parsed.hostname and parsed.scheme in {"http", "https", "socks4", "socks5", "socks5h"}:
                    protocol = parsed.scheme
                    port = parsed.port
                    auth = parsed.username is not None or parsed.password is not None
        except ValueError:
            protocol, port, auth = None, None, None
    captcha = data.get("decaptcha")
    provider = captcha.get("name") if isinstance(captcha, dict) else "default" if captcha is None else None
    if provider not in ("default", "custom", "9kw.eu", "telegram"):
        provider = "unknown"
    modules = shared.get("customModules", [])
    count = len(modules) if isinstance(modules, list) and len(modules) <= 1000 else None
    return {
        "telegram": "configured" if native_notification_ready(session, "telegram") else
                    "unsupported" if telegram else "not_configured",
        "discord": "configured" if native_notification_ready(session, "discord") else
                   "unsupported" if discord else "not_configured",
        "proxy_enabled": active, "proxy_protocol": protocol,
        "proxy_port": port, "proxy_auth": auth,
        "challenge_provider": provider, "registered_extensions": count,
    }
