# Design — session and authentication ownership

States: STOPPED → VALIDATING_SESSION → AUTHENTICATED or NEEDS_LOGIN → ASSISTED_LOGIN → VALIDATING_HANDOFF → AUTHENTICATED; failures lead to retryable PAUSED/FAILED states.

The account lease is scoped to account, world and player. Reuse saved authentication before attempting a new browser login. When manual help is needed, pause the remote worker, notify the local GUI and allow a human to complete login or CAPTCHA. Never bypass a challenge.

Validate the resulting lobby token/session material through the worker without creating a second unrequested game session. If that handoff is unsupported, use an authorized remote browser session instead. Store all secrets outside Git and logs. Model every recovery path in offline mocked tests.
