## ADDED Requirements

### Requirement: Exact revision release verification
A released backend, web client and Mac package SHALL identify their verified compatible source revisions. The project SHALL retain incomplete automated and manual acceptance evidence separately. Manual owner acceptance MAY be deferred but MUST NOT be recorded as passed.

#### Scenario: A required build has not succeeded
- **WHEN** the matching Mac packaging or required CI has not succeeded
- **THEN** the release is not represented as verified and an older artifact is not substituted
