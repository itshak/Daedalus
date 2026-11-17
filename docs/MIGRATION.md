# Migration inventory and public-source policy

**Do not import any runtime account directory or private repository history into this public Git repository.**

## Clean upstream source

- Repository: https://github.com/Ikabot-Collective/ikabot
- Baseline reviewed: upstream 7.7.2, master revision `3ea1e0e` (2026-11-16).
- Relevant proposed (not yet master) work: upstream CLI/IPC and JSON task launch in PRs #499, #502 and #510.
- Bring upstream code in as an explicit tracked import; retain license/provenance; preserve a repeatable upstream merge process.

## Local migration inputs (never committed wholesale)

1. The existing private PySide6 GUI. Port its views, models, resource reports, Selenium-assisted authentication and human CAPTCHA pause with a renamed Python namespace.
2. The production IkaBot checkout with custom GF token and session-handling modifications. Compare each local modification against upstream and port only validated, nonsecret behavior.
3. The production account and tmux setup. Record **design observations only**, not file contents or identifiers. Recreate configuration on the deployed server using secure local provisioning.

## Mandatory review before importing a source file

- Identify upstream ownership and licensing; retain attribution.
- Check for embedded secrets, account identifiers, URLs containing session state, browser cookies, logs, test snapshots or personal data.
- Remove legacy config files and absolute paths.
- Ensure all tests use synthetic accounts/fixtures and make no game-network calls.
- Confirm no second implementation of game actions is introduced.

No game login, existing tmux session, or production task has been changed by this foundation commit.
