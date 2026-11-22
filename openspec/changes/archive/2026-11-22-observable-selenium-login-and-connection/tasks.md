# Implementation checklist

- [x] Audit the private IkaBot Warehouse login fallback and live GUI log behavior without copying secrets or local runtime state
- [x] Add bounded headless-to-visible recovery for CAPTCHA, failed credentials, login form/navigation errors and world timeout
- [x] Route isolated Selenium helper lifecycle and sanitized stages to live desktop Activity and diagnostics
- [x] Keep Chrome and macOS Keychain work off Qt GUI thread and preserve cancellation/watchdog safeguards
- [x] Show Fluent success notification after backend verification and a masked configured-token placeholder
- [x] Add offline synthetic regression tests for headless failure, manual completion, activity logging and token masking
- [x] Update canonical capability specs, operator documentation and this historical OpenSpec record
- [x] Keep unperformed live Gameforge/CAPTCHA/Mac visual acceptance open in existing owner issue #60 rather than claiming it passed

The checklist is scoped to code/spec implementation, not owner-supervised live acceptance.
