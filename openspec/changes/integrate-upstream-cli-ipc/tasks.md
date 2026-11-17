# Tasks

## Upstream engine integration
- [x] Verify upstream PR #499 includes CLI follow-ups #502 and #511.
- [x] Merge its head into the exact stable master baseline without conflicts.
- [x] Port combined public engine files and tests; preserve license and source SHA provenance.
- [x] Do not copy production modifications or account/runtime files.

## Inspectability and tests
- [x] Recognize structured CLI/IPC capability through static source inspection only.
- [x] Keep individual task dispatch disabled until validated schema/worker integration.
- [x] Run candidate CLI/IPC unit tests without any live account.
- [x] Run full combined upstream test suite offline.

## Verification and publication
- [ ] Run updated Daedalus unit tests, lint and OpenSpec checks.
- [ ] Push as `itshak` and obtain clean GitHub CI and security scan results.
- [ ] Review and merge without bypassing required CI.
