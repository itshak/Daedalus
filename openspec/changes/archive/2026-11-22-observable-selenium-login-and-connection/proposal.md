# Observable Selenium login and explicit backend connection feedback

## Problem
Native desktop sign-in can appear to do nothing while the isolated headless Selenium browser runs: the primary Activity timeline ignores most stage messages, subprocess startup/protocol failures are silent and failed headless login does not open Chrome for recovery unless a CAPTCHA element is detected. The Connection screen clears its token field after successful login without a visible success notification or a configured-credential hint.

## Goals
- Restore the owner-owned `itshak/ikabot` warehouse GUI's headless-then-visible login recovery behavior, including non-CAPTCHA failures, while preserving one-account ownership, exact-world validation and a manual-only CAPTCHA.
- Show safe progress from subprocess startup through selected-world and backend verification in the Mac Activity timeline and private bounded diagnostics, with no browser blocking the Qt event loop.
- Confirm a successful backend handshake with Fluent UI feedback and a masked token indicator without duplicating the bearer in Qt input state.

## Constraints
Do not expose passwords, tokens, cookies, arbitrary Selenium errors or account IDs in logs. Do not mark a session authenticated until the backend independently attests the selected player/world. Real Gameforge/CAPTCHA acceptance remains an owner-operated follow-up in issue #60 and is not claimed by this implementation.
