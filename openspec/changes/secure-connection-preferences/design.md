# Secure connection preferences design

The desktop keeps its existing ephemeral bearer transport. Opt-in preference storage uses an owner-private small JSON document containing only the API root URL, validated by the same URL policy as the HTTP client. The bearer token is stored separately in the operating system's keyring through an optional local `keyring` backend. No plain-text fallback is permitted.

A user clicking Reconnect reuses the already authenticated in-memory API client if present; after an application restart, reconnect reads the saved URL and retrieves the token from the keyring only on explicit user action. Failure leaves the app disconnected with a sanitized message, without exfiltrating the OS credential. Forget removes both forms of local preference where possible.

No automatic game request is replayed. All health/account/registry reconnect calls stay in the same off-GUI-thread worker and never resume tasks.
