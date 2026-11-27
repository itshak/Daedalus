# Implementation checklist

- [ ] Audit every web and native page, existing scope and account-specific editors; map exemptions.
- [ ] Implement shared scope model, shell controls, persistence and authorized inventory reconciliation.
- [ ] Wire all relevant reads, aggregation and targets; clear stale previews and guard request races.
- [ ] Integrate explicit reviewed multi-account target selection with Production and existing bulk actions.
- [ ] Test all/one/selected/empty, removed accounts, duplicate player names, refresh/navigation, out-of-scope dispatch prevention, delayed results, native/web accessibility and EN/RU web; run CI.
