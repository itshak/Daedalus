# Engineering-only release consolidation

Use `docs/operation-coverage.json` and the runtime registry as the permanent coverage source. Existing native editors and reviewed contracts are the baseline, not tasks to reimplement. Each remaining option must have concrete source/test evidence, a narrow implementation fix, or an explicit safe unavailable disposition. Keep protected-local tasks local and never create arbitrary remote code or game proxies.

Add offline integration fixtures at actual UI/BFF/API/IPC/session boundaries (synthetic game responses, no live credentials). Distinguish synthetic implementation evidence, published build/rollout evidence, and owner acceptance; do not infer delivery from a launch receipt. Default-on recovery must respect persisted disable/pause, credentials, exclusive ownership and write-ahead fences. Legacy PID-only jobs must remain manual unless trustworthy configuration can be reviewed.

Use the existing web security architecture, local-only credential stores and fixed route allowlists. Assess missing rate limiting, cookie/CSP and audit policy against the deployed Supabase/Vercel setup without reading secret values. Preserve online-only volatile warehouse cache.

All six source proposals are archived as superseded, retaining original unchecked boxes and per-item disposition. Current canonical specs retain their normative requirements, with newer default-on recovery, visible browser fallback and native-only editor requirements taking precedence. Any requirement not verified stays an engineering task or owner acceptance item. No live acceptance gate is waived.
