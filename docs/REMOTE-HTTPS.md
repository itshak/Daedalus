# Stable HTTPS for the Daedalus API (without Mac SSH tunnels)

For remote native clients, the recommended architecture is **HTTPS hostname → trusted authenticated edge → server-side outbound tunnel / reverse proxy → loopback-only Daedalus API**. The Mac stores the API bearer in the OS Keychain after an authorized first connection, and automatically reconnects to the saved HTTPS URL. The client needs no VNC, SSH, port forwarding, or local daemon. The Ikariam worker remains on its own Linux machine.

## Server setup: Cloudflare-managed tunnel example

Use an existing authorized Cloudflare zone and a **dedicated remote-managed Cloudflare Tunnel** for this backend. Set one ingress hostname to `http://127.0.0.1:8765`, followed by a catch-all `http_status:404`. Create a proxied CNAME from the chosen hostname to `<tunnel-id>.cfargotunnel.com`. The tunnel connector runs on the backend host with **host network** access to the locally bound service. It makes outbound connections to Cloudflare; do **not** publish the Daedalus API process on `0.0.0.0` or open port 8765 in the firewall.

A root-owned or operator-owned **0600** tunnel-token file outside the repository (for example `~/.config/daedalus/cloudflare-tunnel-token`) may be mounted read-only into an unprivileged `cloudflare/cloudflared` Docker container. Use `cloudflared tunnel --no-autoupdate run --token-file /run/secrets/cloudflare-tunnel-token`, host networking, no Linux capabilities, read-only root filesystem and `--restart unless-stopped`. Pin an immutable image digest and maintain it under your normal patch schedule. Never print the tunnel token or include it in `docker run` arguments or GitHub Actions logs. Rotate it through Cloudflare when compromised. You may use a systemd-managed official binary instead of Docker with the same local-only origin and token-file protections.

Use the existing strong Daedalus bearer token (at least 32 random characters) for **every** account, task and warehouse endpoint. The public `/api/v1/health` endpoint intentionally discloses only service status. Use extra Cloudflare Access, WAF and rate limits if you operate outside a trusted group; introducing Access service credentials also requires a corresponding secure desktop identity flow. Never use a Gameforge cookie or lobby token as the backend API token. Cache-Control `no-store` and `nosniff` response headers are enforced by the current source; deploy the corresponding backend revision before relying on those additional headers.

## Verification

1. Confirm `systemctl is-active daedalus.service` reports active, `ss -ltn` shows `127.0.0.1:8765` and **not** an externally bound Daedalus port, and the tunnel connector reports healthy without logging credentials.
2. Request `https://your-daedalus-server.example/api/v1/health` with normal TLS verification; expect HTTP 200, `service=daedalus` and a valid public certificate.
3. Request `/api/v1/accounts` **without** a bearer: expect HTTP 401, never account details. Then use the authorized Mac client with its saved Keychain token; expect real account metadata. Do not paste the bearer into shared terminal history or request URLs.
4. Restart only the dedicated tunnel connector to confirm its restart policy works; the Daedalus worker and other IkaBot processes should not be interrupted. **Do not** restart the Daedalus worker to verify tunnel reliability or break an authenticated Gameforge session.

The Cloudflare Tunnel is **server-side**: it is not an SSH tunnel and requires no Mac-side maintenance. Origin authentication depends on the strong API bearer and any additional edge policy you configure; HTTPS alone is not access control. Publicly publishing the account API expands the network attack surface and should be treated as an administrator-approved operation, with a documented revocation and incident response process.

## Native macOS client behavior

The Connection page opens to a single primary **Connect** action. The first successful authenticated HTTPS session stores the exact URL in owner-only local preferences and its bearer in macOS Keychain by default. From subsequent launches, only the **same** saved HTTPS origin is auto-connected; missing/locked Keychain state fails without leaking the token. Explicitly unchecking the Keychain option creates an ephemeral session. No Gameforge login or game task runs from this connection action. Optional local loopback, SSH fallback and an isolated demo remain available for development, behind advanced options.

## Native Mac browser login through trusted HTTPS

Starting the backend with `--enable-native-browser-login` enables an audited, bearer-authenticated, one-use encrypted session handoff API. No *plaintext* Gameforge cookie, password or browser profile is accepted as a field;
the authenticated account-list view may disclose an already verified email
binding, while login-vault endpoints accept and return **only client-sealed
ciphertext**; only a session encrypted with the short-lived server public key and bound to the exact account/world/player/ticket is permitted. All endpoints require the same strong API bearer. Do not enable for public demos or metadata-editing mode. Rate-limit or place an appropriate access policy in front of the authenticated API. All actual game session verification and owner lease enforcement stays on the Linux backend, not on the Mac. See [NATIVE-MAC-LOGIN.md](NATIVE-MAC-LOGIN.md).
