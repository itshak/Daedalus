## ADDED Requirements

### Requirement: Native Mac browser login is an explicit first-class GUI action

For an enabled selected account and a capable authenticated backend, the GUI SHALL offer **Sign in on this Mac**, open an off-the-record Gameforge HTTPS browser, allow human challenge completion, and prompt for explicit encrypted handoff approval. It SHALL not read passwords/MFA or write world session cookies to preferences, log output, local accounts files, or an ordinary API request. A disconnected, demo, or non-opted-in server SHALL disable this action.

#### Scenario: User selects an account
- **WHEN** the operator selects an enabled account on a capable HTTPS backend
- **THEN** one native Mac browser sign-in action is available without SSH/VNC instructions

#### Scenario: Native browser is cancelled
- **WHEN** login is cancelled or expires
- **THEN** the browser is destroyed, session handoff is discarded, and no game task is replayed

### Requirement: macOS preview bundles private browser runtime

The signed-preview build SHALL include the Qt WebEngine renderer helper and cryptography dependencies, with synthetic CI checks that do not access real Gameforge credentials.

#### Scenario: macOS preview build
- **WHEN** the native .app is built in CI
- **THEN** the app package includes Qt WebEngine modules and its process helper
