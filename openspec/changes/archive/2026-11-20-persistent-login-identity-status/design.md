# Design

- Keep static account metadata secret-free; the accounts API reads only a
  verified email binding from the protected store for authorized clients.
- Client produces AES-256-GCM ciphertext bound to exact HTTPS origin,
  account ID and world. Per-account 256-bit keys remain only in macOS Keychain.
- Server double-encrypts opaque records using the existing systemd credential
  adapter. GET login-vaults returns ciphertext only, and POST per-account
  requires a verified email association before storing.
- A stolen API bearer alone cannot decrypt Gameforge passwords; lost Mac keys
  cannot be recovered from the server.
- Worker attachment, game authentication and account enabling are separate
  states with check/X/unknown/waiting icons and explanatory tooltips.
- Live deployment needs controlled restart and user acceptance.
