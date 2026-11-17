# Security baseline

## Public-source policy

This repository is public. Never commit real credentials, passwords, `gf-token-production` values, account environment files, browser cookies, saved sessions, account snapshots containing private identifiers, or production logs.

Use test fixtures with synthetic identities, deterministic mock tokens and offline HTTP recordings stripped of sensitive data. A fixture or masked sample must not be reversibly derived from a real token.

CI has no real game accounts and MUST NOT log in to Gameforge. Dependabot/dependency review and secret scanning complement, not replace, code review.

## Runtime design

Account identities and encrypted/protected session material are managed by the backend, outside the source tree. Desktop secrets use the operating system's secure credential storage when feasible. Local IPC and remote HTTP APIs require authentication, authorization, rate limiting and least privilege.

An interactive login fallback may require the user to solve a CAPTCHA. It must not try to bypass the challenge. A new game login must coordinate with the existing session owner to prevent displacement.

## Reporting

Report potential vulnerabilities privately to project maintainers rather than posting tokens, credentials or exploitation details in public issues.
