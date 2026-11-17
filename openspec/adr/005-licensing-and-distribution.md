# ADR-005: GPL project with explicit third-party provenance

**Status:** Accepted for original code; desktop dependency distribution audit pending

## Decision
License Daedalus-original code under GPL-3.0-only. Preserve upstream IkaBot's MIT license, authorship notices, and all other third-party licenses. The PyPI distribution and import namespace will provisionally be `daedalus`; the name must be accepted by PyPI before a release. Keep releases approval-gated and never publish the legacy `ikabot` package under our project credentials.

## Consequences
The complete set of desktop dependencies (including Fluent Widgets licensing) must be audited before distributing combined binaries. The original MIT engine attribution survives any later GPL redistribution.
