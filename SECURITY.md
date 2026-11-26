# Security Policy

## Supported versions

Daedalus is in **beta (0.1.0)** and has no supported stable release. Security reports about the current default branch and experimental builds are still welcome. Do not assume the project is suitable for production accounts or public network exposure.

## Privately report a vulnerability

Use GitHub's enabled **[Report a vulnerability](https://github.com/itshak/Daedalus/security/advisories/new)** workflow. It creates a private security advisory for maintainers to review. **Do not open a public issue with exploit details, credentials, session data, or private account material.**

Include a minimal reproduction using mock or synthetic data, affected version/commit, security impact, and any suggested remediation. Never attach actual Gameforge cookies, bearer tokens, passwords, or production logs.

We cannot promise a specific response or remediation deadline during beta. Maintainers will triage reports and coordinate public disclosure after mitigation when feasible.

## Security baseline

Review [docs/SECURITY.md](docs/SECURITY.md) for the repository's credential, runtime, and CI safeguards. The desktop and controller are read-only by default; task and account-editing capabilities require separate explicit opt-ins. Remote access requires a protected network path.
