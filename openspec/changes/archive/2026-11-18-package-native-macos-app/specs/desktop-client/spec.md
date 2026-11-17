## ADDED Requirements

### Requirement: Reproducible native macOS preview
Daedalus SHALL provide a macOS application bundle built directly from a checked-out source revision and a named desktop entry point.

#### Scenario: CI preview build
- **GIVEN** a clean source checkout with no account credentials
- **WHEN** the macOS packaging job runs
- **THEN** it produces an identifiable Daedalus.app archive without running Ikariam, modifying /Applications, or loading account sessions

### Requirement: Preview signing is not production notarization
Mac packaging SHALL distinguish local ad-hoc signing from a developer-signed and Apple-notarized release.

#### Scenario: User obtains a CI preview artifact
- **WHEN** the user downloads the app artifact
- **THEN** documentation explains that it is a preview and may be blocked by macOS Gatekeeper without developer notarization
