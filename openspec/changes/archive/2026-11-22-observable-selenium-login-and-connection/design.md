# Design

1. **Isolated auth control.** Preserve the existing `SeleniumLoginWorker` child process, one account at a time. Emit fixed machine-readable stages on process creation, saved-credential lookup, Chrome startup, lobby/form submission, world navigation and error. The desktop only displays allowlisted stage names, not child exception bodies.
2. **Fallback policy.** Reserve a bounded portion of the 240-second login budget for the headless attempt (at most 90 seconds by default), then open one fresh visible Chrome on CAPTCHA or failed login/form/world navigation. Let a human correct credentials, solve the CAPTCHA or otherwise complete the visible login. Manual input is not automated CAPTCHA resolution. Keep waiting until a validated exact-world cookie exists, cancellation or final timeout.
3. **Activity and private log.** The primary Activity timeline accepts fixed sanitized login stage codes with account-category timestamp/severity. The existing queued Qt handler and rotating per-user desktop log retain technical events. Never parse or display raw child stderr.
4. **Connection UX.** A successful authenticated API handshake invokes the existing Fluent `InfoBar.success`. The LineEdit clears the actual bearer, then shows a dotted placeholder indicating either a Keychain-saved token or an active ephemeral connection. Blank input still triggers exact-origin Keychain reuse, never a fabricated mask string.

## Safety and verification
- Tests use fake browsers, fake login credentials and offline IPC; no real Gameforge interaction.
- No token, cookie, password or account ID is emitted in new log entries.
- User cancellation and non-verified sessions do not enable task dispatch.
- Owner real-account login and live-task acceptance are tracked separately by issue #60.
