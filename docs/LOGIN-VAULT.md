# Persistent encrypted Gameforge logins

Daedalus saves a **Mac-encrypted copy** of an opted-in Gameforge login in the
backend's **host-persistent protected credential store**, while the Mac continues
to own Selenium headless Chrome. **Neither the API nor the Linux daemon sees a
plaintext Gameforge password.** Both request and response fields contain only
AES-256-GCM ciphertext. The key is generated independently for each trusted HTTPS
origin + account ID + world and stored **only** in the originating macOS Keychain.
The ciphertext uses that exact identity as authenticated additional data. The
server encrypts the received ciphertext again with the machine-bound systemd
credential store. There is no plaintext TOML, JSON, environment variable, log
or CLI password storage.

After independently verified game login, Daedalus can save the sealed copy
automatically when **Remember securely in Keychain and encrypted server backup**
is selected (the default). The protected email binding is stored separately and
may be returned in the bearer-authenticated accounts API for table identification
and email prefill. Credentials saved earlier in the Mac Keychain can be migrated
without a game login through **Accounts → More → Back up saved logins to server**.
This migration runs in the background, requires existing authenticated server
email bindings, and reports counts without revealing emails or passwords.

On reconnect, the Mac fetches sealed records through the authenticated
GET /api/v1/login-vaults endpoint. If a local Gameforge password is absent but
the corresponding Mac vault key remains in Keychain, it decrypts the record in
memory and logs in headlessly, opening Chrome only for a detected CAPTCHA.
POST /api/v1/accounts/{id}/login-vault takes only confirmed, version, nonce and
ciphertext and requires an existing independently verified email binding.
The backend never exposes a decryptable password or accepts a raw password API
field. Vault records are invalidated by account ID/world/player identity changes.

**Limitation:** The backup is usable **only from the Mac that holds its vault
key**; moving to a new Mac, resetting Keychain, or changing the backend HTTPS
origin requires a new credential entry. This avoids making a stolen Daedalus
API bearer sufficient to obtain Gameforge passwords. Do not export or share Mac
vault keys. The server holds no recoverable passwords for historical accounts
that never opted in; only previously verified email/world-cookie bindings can
be displayed without a fresh Gameforge login. The app cannot reconstruct
missing passwords or invent unbound email identities.

## Deployment and availability

The backend requires --enable-native-browser-login and the existing
systemd host-encrypted credential store. Install the new source, confirm that
the credential key remains durable, and perform a controlled service restart
only when there are no running or uncertain tasks. Never reset the encrypted
store or overwrite existing email/world cookie bindings as part of deployment.
A new API server that lacks the feature or has unavailable protected storage
does not prevent local Mac Keychain sign-in; only encrypted server backup will
be unavailable.

Source and synthetic tests establish encryption, scope, fail-closed behavior,
authentication and API response contents. Live Gameforge login and Mac Keychain
usage must be verified separately by the owner.
