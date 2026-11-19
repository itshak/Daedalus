# Protected Linux daemon credentials (persistent across service restarts)

The Linux daemon can use an **opt-in machine-bound encrypted systemd credential store** instead of GNOME Secret Service's volatile graphical-session collection. The native Mac client still uses macOS Keychain for its separate Daedalus API token. Neither the macOS Keychain nor server-side credential storage requires SSH or VNC forwarding.

## Architecture and security

- `systemd-creds encrypt --with-key=host` wraps a fresh 32-byte AES-GCM encryption key in a **root-owned host-encrypted** credential at `/etc/credstore.encrypted/daedalus-store-key` (mode `0600`). The system's root-owned systemd host secret must be protected and included in trusted disaster-recovery procedures. This uses host software-key protection, **not** a hardware TPM assertion.
- The daemon's `LoadCredentialEncrypted=daedalus-store-key:/etc/credstore.encrypted/daedalus-store-key` loads that key into a transient, service-scoped `CREDENTIALS_DIRECTORY` without copying it to a plaintext app config or environment variable. `User=debian` can use it only inside the authorized service.
- `DAEDALUS_PROTECTED_STORE_DIR` explicitly opts the server into `SystemdCredentialStore`. Saved account associations and independently verified world cookies are encrypted with AES-256-GCM, each with a fresh random nonce and additional authenticated data binding the account-scoped identity and service name. Filenames are SHA-256 hashes of that identity. Secret records are owner-only (`0600`) in an owner-only (`0700`) directory.
- The adapter implements the existing keyring-compatible `set_password` / `get_password` / `delete_password` protocol. **If the encrypted key is missing, corrupt or has not been passed by systemd, login fails closed.** There is no fallback to plaintext JSON/TOML or the volatile session keyring when encrypted mode is selected.
- The protected store is still decryptable by a compromised authorized service user while running; it is not a remote hardware security module. Do not back up the encrypted key file without also protecting the machine-bound host key material. Protect private IkaBot legacy saved-session files independently.

## Service example

Install the `daedalus[server]` dependencies, including `cryptography`, then configure a root-owned encrypted 32-byte key with systemd's native credential tooling. Never put the raw key in shell arguments, environment variables, GitHub Actions logs, the repository or user-visible files; generate it via a root-only temporary file on a trusted `tmpfs`, encrypt with `systemd-creds`, validate the round-trip without printing it, then securely discard the temporary key.

Apply this example drop-in (substitute the intended private data directory) to `/etc/systemd/system/daedalus.service.d/20-encrypted-credentials.conf`:

```ini
[Service]
Environment=DAEDALUS_PROTECTED_STORE_DIR=/home/debian/.local/share/daedalus-protected-credentials
LoadCredentialEncrypted=daedalus-store-key:/etc/credstore.encrypted/daedalus-store-key
```

The main `ExecStart` should retain the fixed-account flags, HTTPS-loopback binding and `--enable-native-browser-login` if the Mac's human login should be available. For a headless server, remove the old `Wants=vncserver.service`/`After=vncserver.service` dependency from the main service unit as well: the native browser lives on the Mac.

Before restarting a real worker, migrate existing protected associations **only with an authorized, local-only utility** that can read the old secret provider and write the new encrypted store directly in the same OS user context. Never print or upload values. If an old cookie exists only in a private upstream IkaBot saved-identity file, require a fresh TLS-verified, cookie-only read-only world/player attestation before encrypting it. A legacy cookie cannot be accepted merely because a JSON file contains it. Verify readback of the new encrypted records without logging values. Preserve an owner-only ledger backup and inspect any uncertain tasks before a service restart.

Test systemd's actual credential decryption with a **separate** transient service under the intended `User`, using the same `LoadCredentialEncrypted` setting and only reporting boolean presence. After a controlled restart, confirm one authenticated session, exact world/player, read-only warehouses, zero unresolved task receipts and the opt-in browser-login capability. Avoid starting a second owner or auto-replaying a task. The original service's live worker must stop before its replacement starts.

## Operator verification

`daedalus doctor --deployment-check --protected-store-directory /private/encrypted/store` reports read-only metadata. `task_ledger.status=clear` and `keyring_durability=host_encrypted_collection_present_unverified` indicate no unresolved task requests and existing private ciphertext files; these alone **do not prove the host can decrypt them**. Successful service restoration and read-only game attestation provide stronger evidence. A true host-reboot acceptance, native Mac login/MFA/CAPTCHA and a single real task trial must still be recorded separately in [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md).

The systemd credential persists across ordinary daemon restarts as long as the server's machine-bound host key is preserved. A full host reboot was deliberately **not performed** during Monjo remediation because it would interrupt other production bots on the same machine. No Telegram/Discord credentials were migrated or modified.

The `daedalus sessions ...` CLI deliberately does **not** inherit the systemd service key. Direct interactive commands outside the configured transient service must not copy an encryption key into a shell environment. Use the native Mac browser login for credential renewal, or an authorized service-scoped maintenance process with `LoadCredentialEncrypted`.
