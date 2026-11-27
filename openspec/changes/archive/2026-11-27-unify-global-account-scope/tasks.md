# Implementation checklist

- [x] Audit every web and native page, existing scope and account-specific editors; map exemptions.
- [x] Implement shared scope model, shell controls, persistence and authorized inventory reconciliation.
- [x] Wire all relevant reads, aggregation and targets; clear stale previews and guard request races.
- [x] Integrate explicit reviewed multi-account target selection in existing bulk actions; provide reusable scoped targets for the separate Production change.
- [x] Test all/one/selected/empty, removed accounts, duplicate player names, refresh/navigation, out-of-scope dispatch prevention, delayed results, native/web accessibility and EN/RU web; run CI.


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
  Python lint and strict OpenSpec validation. 239 native regression tests and two expanded authenticated browser E2E scenarios passed. Both hosted engine versions, macOS native/build, packaging and security checks passed on the initial revision. Corrected native test fixtures and OpenSpec status inventory; fresh hosted Python matrix passed across all nine Python/OS combinations at 44da1e4. Engine, web, native UI, browser, packaging, security and OpenSpec checks also passed. The final macOS packaging and archival revision checks remain merge gates. No live game acceptance or release is claimed.

## Page audit

- Web: overview, warehouse snapshots/exports, military, activity, world reports,
  account-bound settings, workflow editors and review queue use the shell roster.
  Account management has an explicit manage-all escape; release, authentication
  and controller health remain global. The native Home, Warehouses, Military,
  Activities, task views and account-specific settings receive the scoped roster;
  Connection and appearance preferences remain global.
- Reads and review queues reset on scope changes, with native generation checks
  and web keyed components. Existing running operations are not cancelled.
- Native scope changes during an active Selenium sign-in cohort are deferred
  until the sign-in finishes; this preserves the fixed authenticated cohort.
- Production-specific inventory and reallocation are the next separate proposal.
