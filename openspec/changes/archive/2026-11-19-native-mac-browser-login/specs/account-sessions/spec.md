## ADDED Requirements

### Requirement: Native Mac human browser session recovery uses one authoritative worker

The client SHALL allow a human to sign in to official Gameforge pages using a temporary native Mac browser without automated CAPTCHA or password entry. It SHALL select only the exact enabled account world session with explicit transfer confirmation. The backend SHALL verify the fresh server-rendered player/world independently before accepting the cookie. A dedicated worker SHALL retain its original lease and SHALL not replay old tasks.

#### Scenario: Human finishes Mac sign-in
- **WHEN** a Mac user signs in and authorizes an encrypted world-cookie transfer
- **THEN** the backend verifies the actual selected player's game-world identity before saving the session or rebinding the existing dedicated worker

#### Scenario: Session mismatches the player
- **WHEN** game-world verification fails or the envelope is expired or replayed
- **THEN** the old verified cookie and authoritative worker lease remain protected; no task is started

### Requirement: Dedicated-worker recovery rejects active or uncertain work

The backend MUST refuse native browser recovery of a dedicated worker with running, stopping, dispatching, or unconfirmed operations. It MAY pause an idle worker under its existing exclusive identity lease, and MUST keep the lease on failed or uncertain rebind without starting a competing worker.

#### Scenario: Unconfirmed task exists
- **WHEN** an operator requests browser recovery while a durable task receipt remains unconfirmed
- **THEN** recovery is refused without altering the worker or starting another game operation
