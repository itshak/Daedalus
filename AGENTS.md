# AGENTS.md — Daedalus engineering constitution

## Mission
Build one maintainable Daedalus application: existing public IkaBot operations as the sole game engine; a local/remote multi-account controller; a full-featured native desktop UI; safe interactive authentication recovery.

## OpenSpec workflow
- Read applicable `openspec/specs/*/spec.md` and `openspec/adr/` before coding.
- Read and update an active `openspec/changes/<change-id>/` proposal, design, delta specs and tasks for substantive changes.
- Workflow: explore → propose → apply → verify → archive.
- Validate with `openspec validate --all --strict --no-interactive`.
- Prefix commits implementing a change with `[change-id]`.
- Use English, normative SHALL/MUST requirements and Given/When/Then scenarios.

## Architectural constraints
1. IkaBot's upstream game modules remain the only game-operation engine. The controller may plan, schedule, validate, and orchestrate operations, but MUST NOT independently duplicate game networking.
2. Each account/world/player identity has a single active authenticated game-session owner, with locks, recovery, and explicit state transitions.
3. The desktop client uses one versioned API contract regardless of local or remote deployment.
4. Authentication MUST support restoration and human-assisted recovery; upstream password login is not assumed functional. Do not bypass CAPTCHAs.
5. Server-side policies SHALL be restart-safe, with state reconciliation and no duplicate state-changing actions.
6. Packaging uses unique distribution and import namespaces. Never shadow the upstream `ikabot` package with the legacy GUI's package of the same name.

## Security and provenance
- **Never read, print, upload, or commit** real secrets, passwords, saved sessions, cookies, GF tokens, browser profiles, personal account configuration, server credentials, or runtime logs.
- The older private GUI and modified production server checkout are **local migration sources only**. Review and port safe code selectively; never import their git history or runtime trees wholesale.
- Never expose an engine IPC or game proxy endpoint on a public interface without strong authentication and access controls.
- Public CI MUST run offline synthetic tests only: no game logins and no production credentials.
- Retain upstream MIT license notices and document the provenance of every imported component.
- Preserve the existing production tmux sessions and installations until a separate, tested migration/cutover change authorizes the transition.

## Verification
- Run `python -m pytest`, `python -m ruff check src tests`, and OpenSpec validation before considering tasks complete.
- Add migration tests for account isolation, auth fallback, CAPTCHA wait, CLI/IPC dispatch, session expiry, idempotency and desktop APIs before bringing real accounts onto a new build.
