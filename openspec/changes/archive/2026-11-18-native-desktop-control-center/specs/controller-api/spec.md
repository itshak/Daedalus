## ADDED Requirements

### Requirement: Desktop bearer tokens use protected transport
The desktop SHALL refuse to send an API bearer token over plaintext HTTP to a non-loopback address.

#### Scenario: User enters remote HTTP URL
- **WHEN** the user enters `http://example.org` with an API token
- **THEN** the client refuses the connection before sending any request

### Requirement: Remote errors do not leak credentials
The desktop MUST sanitize connection and API errors and SHALL NOT print response bodies or bearer tokens in log or exception messages.

#### Scenario: Server includes a secret in an error body
- **GIVEN** a remote server responds with a private token in the body
- **WHEN** a request fails
- **THEN** the UI displays a generic status error without the token
