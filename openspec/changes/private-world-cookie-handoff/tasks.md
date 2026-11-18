# Tasks
- [x] Add a safe in-memory game-world cookie override exclusively for cookies-only IkaBot restoration.
- [x] Add local masked terminal import and OS-keyring-only account/world/player bindings.
- [x] Validate current game-world cookie under the account lease before storing, preserving old credentials on failure.
- [x] Enable safe saved-session probes to reuse a verified imported cookie and explicitly delete the keyring binding.
- [x] Test no lobby loginLink, malformed/cross-account values, terminal consent, sanitized failures, identity isolation and backward compatibility offline.
- [ ] Run all Daedalus/engine suites, Ruff, strict OpenSpec, packaging and protected macOS CI.
- [ ] Merge as itshak; archive completed work and synchronize canonical specs/docs.
