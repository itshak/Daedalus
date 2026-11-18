# Try the native Daedalus app without a backend setup

Open the Daedalus Mac preview and choose **Connection → Try offline demo — no game login**. The app starts a temporary private demo API on your own computer, automatically supplies a random in-memory bearer token, and connects itself.

You will see **SYNTHETIC DEMO** in the title bar, connection status and warehouse screen. Both example accounts and every city/warehouse value are fictional. Explore Accounts, Warehouses, the 220K filter, island grouping, operation catalog and report exports without IkaBot credentials or a running engine. Task controls remain disabled.

The demo never reads your account config, IkaBot IPC file, browser profile or cookies, never makes Gameforge requests, and cannot run game automation. The backend listens on an OS-selected loopback-only address (127.0.0.1) for the life of the native app. The demo bearer token exists in memory only, cannot be saved using Remember connection, and is not printed or placed in a URL. Closing the app stops the temporary backend.

For Python launches, install the desktop extra with built-in server dependencies using `python -m pip install -e ".[desktop]"`; the macOS preview bundles the same dependencies. If you prefer a separately running backend, the original `daedalus serve --demo` and manual connection flow remains supported.

This is still an unnotarized macOS preview and **not** a production Gameforge bot. Real-account functionality requires a separately authorized, authenticated IkaBot engine session and opt-in backend.
