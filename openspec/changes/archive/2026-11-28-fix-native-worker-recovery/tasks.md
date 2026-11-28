## 1. Implementation
- [x] Adopt native browser-cookie workers into the automatic recovery supervisor and shared task controller.
- [x] Fence periodic cookie restoration against durable recovery events and stop invalid worker descendants.
- [x] Refresh native session and worker indicators and fail closed on polling errors.
- [x] Preserve explicit manual fallback after failed automatic recovery.
- [x] Add synthetic regression tests for native worker loss, grace, manual fallback, API connection status and desktop polling.
## 2. Verification
- [x] Pass the complete offline suite and required GitHub CI on the implementation revision (bad4532; all applicable checks passed).
- [ ] Verify production deployment and real browser takeover / lobby-token recovery; validate the new Mac build.

Owner explicitly deferred remaining human-only acceptance on 2026-11-28; see [issue #124](https://github.com/itshak/Daedalus/issues/124). Unchecked tasks are unperformed, not passed. The consolidated revision must also pass CI before merge.
