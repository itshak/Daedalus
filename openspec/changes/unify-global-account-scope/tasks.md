# Implementation checklist

- [ ] Audit every web and native page, existing scope and account-specific editors; map exemptions.
- [x] Implement shared scope model, shell controls, persistence and authorized inventory reconciliation.
- [ ] Wire all relevant reads, aggregation and targets; clear stale previews and guard request races.
- [ ] Integrate explicit reviewed multi-account target selection with Production and existing bulk actions.
- [ ] Test all/one/selected/empty, removed accounts, duplicate player names, refresh/navigation, out-of-scope dispatch prevention, delayed results, native/web accessibility and EN/RU web; run CI.


## Implementation evidence

- Web and native shell working preferences, scoped views and explicit manage-all
  account administration are implemented. The native scope is also exposed
  through the existing report settings shortcuts. Existing reviewed operation
  endpoints and controller authorization are unchanged.
- Web account-bound requests and editors are keyed to the working context;
  native asynchronous reads carry a working-context generation. The alert batch
  editor freezes its reviewed target list. The future Production page is not
  implemented in this change.
- Local evidence: web typecheck, 93 web tests, Next.js production-mode build,
  synthetic authenticated browser E2E (including city isolation, empty scope,
  refresh and approval invalidation), focused native scope/preferences tests,
  Python lint and strict OpenSpec validation. Full native/Python/engine,
  security and hosted CI still require verification. Keep the proposal active
  until the remaining audit and verification gates are complete.
