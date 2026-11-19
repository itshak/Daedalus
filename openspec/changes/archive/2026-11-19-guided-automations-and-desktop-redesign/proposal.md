# Guided automations and desktop redesign

## Why

The first owner-authorized live task trial exposed a nonsecret prerequisite failure that the controller mislabeled as an uncertain launch. The desktop also exposes a read-only operations table, duplicate task views and mandatory raw JSON authoring instead of a guided workflow. Users need understandable, low-friction controls without weakening single-account ownership, idempotency, and explicit consent.

## What Changes

- Add protected read-only task prerequisite diagnostics that return only restricted booleans/reason codes, never notification tokens, game HTML or credentials.
- Reject deterministic prerequisites *before* request reservation and preserve durable `unconfirmed` behavior for genuine ambiguous transport errors.
- Redesign native navigation around an account-first dashboard and a guided Automations workspace, with category filters, forms, default values, an optional advanced JSON editor, clear status/help, and explicit start/stop approval.
- Replace day-to-day Mac SSH-tunnel setup with direct HTTPS and default secure Mac Keychain token saving/automatic reconnection; retain SSH only as an advanced private-network fallback.
- Keep other game accounts and existing running workers untouched; update tests and docs and deploy only after checks.

## Out of scope

- Human-only CAPTCHA, automatic password handling, setting Telegram/Discord secret keys through public REST, unattended session recovery after reboot, real task launch without owner authorization, or automatic reconciliation of prior uncertain requests.
