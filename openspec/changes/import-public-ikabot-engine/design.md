# Design — upstream engine import

Import a known public upstream revision via a tracked source mechanism; record SHA and retain original LICENSE, copyright and notices. Do not nest a Git repository inside the monorepo. Establish repeatable upstream-update procedure.

The proposed JSON CLI/IPC is not in reviewed master; test candidate patches with fake sessions and account identities before deciding whether to adopt them. Preserve legacy public IkaBot task implementations and keep game HTTP logic inside the engine.

Port local production session/login improvements one audited patch at a time. Never copy .env account files, saved sessions, tokens, cookies, logs or private data. Add mocked integration tests before any deployment.
