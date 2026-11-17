# Tasks
- [ ] Review and license-audit existing GUI sources and dependencies.
- [x] Port the reviewed Fluent navigation, read-only accounts/warehouse/operations views and CSV/JSON exports into `daedalus.desktop`.
- [ ] Finish remaining legacy GUI parity: account editors, island grouping and text exports.
- [x] Implement versioned local/remote API client with masked in-memory bearer token and protected transport.
- [ ] Add optional secure persistent connection preferences and reconnect UX.
- [x] Implement UI filtering and CSV/JSON exports with null distinct from zero, using backend snapshot contract.
- [ ] Wire the real authenticated engine warehouse snapshot provider.
- [ ] Add task registry forms and dedicated workflow screens.
- [x] Test native GUI and .app packaging in macOS CI and validate OpenSpec.
