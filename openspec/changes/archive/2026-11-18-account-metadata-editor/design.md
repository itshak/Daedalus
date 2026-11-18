# Safe account metadata editing design

The existing public TOML schema is the single source of truth. A new opt-in `--enable-account-editing` mode exposes a protected GET/PUT configuration endpoint and advertises edit capability to the native GUI. The controller never accepts passwords, emails, cookies, session material or unknown keys. An optimistic SHA-256 generation over canonical metadata prevents overwriting another editor's changes. A local interprocess file lock and atomic owner-only write prevent partial TOML.

The AccountSessionCoordinator must be idle and task control must not be enabled. After persistence succeeds, the backend reloads its metadata map and coordinator identities without authentication attempts. Reject active leases. The native editor only holds the nonsecret generation and validated rows in memory, and asks for confirmation before posting changes from a Qt worker thread.

A second backend that has independently authenticated a game worker cannot be coordinated by local metadata locking; the user must use a single authoritative Daedalus controller for game tasks. No production worker or Gameforge session is touched by this change.
