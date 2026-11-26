# ADR-007 — Version-gated Vercel deployments

Status: Accepted.

Ordinary development commits must continue to run offline CI without triggering hosted builds. A reviewed main merge increasing the aligned web version triggers the production build. Missing history, invalid version metadata, non-production environments and non-main branches skip. The project-level ignored-build setting and checked-in configuration enforce the same decision. Operators can explicitly redeploy a reviewed SHA without bypassing authentication or changing the persistent gate. No release tag movement, secret-bearing CI or automatic backend restart is introduced. Public beta publication and coordinated production rollout remain explicit approvals.
