# Private local handoff of a manually authenticated game-world cookie

## Why
The native desktop's assistance acknowledgment cannot transfer a cookie from an independently authenticated browser into IkaBot. Daedalus needs a narrowly scoped, local-only mechanism for an operator to validate and store an existing browser-authenticated world cookie without issuing a new Gameforge loginLink or sending credentials through the remote controller API.

## What changes
- Extend the Daedalus-vendored engine's explicit cookies-only restoration mode to accept a validated in-memory world cookie override for exactly one saved account/player/world, never in the normal upstream login path.
- Add a masked, interactive terminal workflow `daedalus sessions bind-world-cookie ACCOUNT --confirm-read-only-network` that imports a manually copied existing `ikariam` cookie from the operator's own browser. No cookie appears in process arguments, API payloads, logs or TOML.
- Validate the cookie through the same exact world/player read-only probe under the host-local account lease before it is saved to a dedicated OS keyring entry scoped to the account identity. Failed verification cannot replace the previous verified binding.
- Allow future confirmed saved-session probes to use the OS-protected world cookie when one exists, and provide explicit local deletion.
- Refuse noninteractive terminals, malformed tokens, missing saved IkaBot user records, active Daedalus leases and identity mismatch.

## Modified capabilities
- `account-sessions`: verified, lease-bound local cookie handoff.
- `engine-integration`: optional safe per-world cookie override without lobby fallback.
- `security-boundaries`: OS credential store only, hidden prompt, no controller API cookie transport.

## Non-goals
No Selenium/Playwright browser automation, CAPTCHA bypass, Gameforge account password collection, remote browser cookie transfer, new session worker creation, task replay or production migration. User completes login in their own browser before using this local handoff.
