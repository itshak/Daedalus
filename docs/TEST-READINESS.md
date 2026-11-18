# Check your Daedalus preview offline

The early `daedalus doctor` implementation contained hardcoded pre-implementation claims. It now reports installed preview capabilities and the presence of optional packages. It **never** checks your real Gameforge account, saved cookies or private account configuration.

```bash
python -m pip install -e ".[server,client]"
daedalus doctor
```

The JSON distinguishes implemented code from installed dependencies. It identifies engine/CLI, native desktop, opt-in existing-session IPC/task/monitor support and the absent new-worker bootstrap/automatic browser login. `live_accounts_configured: null` means **not inspected**. A preview is not production-ready because a diagnostic passes.

To test the backend without a game login:

```bash
daedalus doctor --smoke
```

This uses FastAPI's in-process test client and fictional demo users. It checks bearer authorization, demo-only mode, fake accounts, capabilities and warehouse reporting, without Gameforge requests or binding a TCP port. Missing optional test dependencies result in a sanitized failure with a nonzero exit. It is not a native Qt smoke; the latter runs in protected macOS CI.

For an interactive desktop preview, run `daedalus serve --demo` with a newly generated backend bearer token and connect the installed native app to localhost. See [synthetic desktop demo](SYNTHETIC-DEMO.md). **A synthetic test does not prove real game account authentication.**
