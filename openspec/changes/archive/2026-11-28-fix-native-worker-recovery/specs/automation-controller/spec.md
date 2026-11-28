## ADDED Requirements

### Requirement: Native session loss uses the existing safe-job reconciliation

Native worker recovery SHALL use the existing desired-state, protected credential, grace and uncertain-receipt fences. Automatic restoration SHALL NOT promote previously manual-only warehouse-fill records or infer accepted cargo from worker presence.

#### Scenario: Native worker reauthenticates

- **GIVEN** a native worker with a durable loss event and captured desired jobs
- **WHEN** the exact account is independently reauthenticated
- **THEN** only eligible jobs with proven remaining work and no unresolved receipts SHALL be considered for restoration.
