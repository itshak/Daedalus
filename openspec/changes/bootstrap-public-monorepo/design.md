# Design — public foundation

## Repository boundaries
Create a fresh `main` history. Source files contain only newly written design documentation and offline Python skeleton code. The existing private GUI and modified production server checkout are not Git remotes and must not be copied wholesale.

## Package
Use `src/daedalus` as the new package namespace and `daedalus` as the entry point. Keep `engine`, `server` and `desktop` as future import boundaries. The original GUI also uses `ikabot` for its import namespace; rename it during migration to avoid collisions with the engine.

## OpenSpec
Reuse the `spec-driven` project structure and workflow from BlindBase/cbvault: `openspec/config.yaml`, `openspec/adr/`, `openspec/specs/<capability>/spec.md`, and active `openspec/changes/<change>/` proposals with design/tasks/delta specs. All substantive changes are validated.

## CI
- Python tests + lint on Ubuntu, Windows and macOS using synthetic data only.
- Separate OpenSpec validation job.
- Static build/package smoke checks from checkout source.
- Read-only workflow permissions and no credentialed live login smoke tests.
- Publish workflows are deferred until artifacts, package identity and provenance are verified.

## Migration safety
Real account files, GF token secrets, saved sessions, cached browser state, log files and developer machines must remain outside Git. Retain all upstream MIT notices when importing engine code in a later change.
