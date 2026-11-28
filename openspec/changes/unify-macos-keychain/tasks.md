# Tasks
- [x] Audit per-account Keychain reads, existing server vault and isolated login protocol.
- [x] Implement single master key and authenticated owner-private encrypted records; migrate existing connection, credential and envelope-key items without destructive migration.
- [x] Reuse the unlocked master across isolated browser helpers and avoid repeated permission requests after denial.
- [ ] Verify synthetic bulk sign-in, migration, corruption, denied access and exact account isolation, plus CI.
- [ ] Verify first-time authorization and legacy migration on physical macOS; verify bulk sign-in after restart and upgrade.

Focused synthetic validation: 22 tests passed (shared vault, connection preferences, OpenSpec hygiene). Ten-account test verifies one master item and no legacy queries on repeat; migrated server envelope keys retain original binding; denial, missing master and tampered records fail closed; real QThread/subprocess pipe carries the unlock result without a Qt signal. Existing legacy ACL approval and physical Mac acceptance remain unverified.
