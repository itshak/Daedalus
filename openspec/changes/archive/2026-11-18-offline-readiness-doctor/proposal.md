# Accurate offline readiness diagnostic and synthetic API smoke

## Why
The current `daedalus doctor` still claims the engine is not integrated, the native desktop does not exist, and the only backend mode is a read-only controller. These claims are stale after multiple protected milestones and mislead operators trying to test the stack.

## What changes
- Report truthful static preview capabilities: engine overlay, opt-in existing-session IPC/task management/monitoring, optional dependency installation and native GUI presence. Do not claim new worker bootstrap, automatic login or production readiness.
- Mark private account status and real game verification as *not checked*, not false.
- Add explicit `doctor --smoke` exercising real FastAPI routes with isolated synthetic demo provider and in-process HTTP test client, checking bearer enforcement, accounts, capabilities and warehouse reporting.
- Nonzero exit on missing test dependencies or synthetic failure, with sanitized errors.

## Scope
- `project-foundation`: offline-ready setup diagnostic and smoke.

## Non-goals
Real game authentication, new worker bootstrap, browser automation, production migration and remote deployment.
