# AI-DLC v2 Engine launch materials

Status: alpha publication draft. Re-run security, provenance, history, package,
and demo checks on the exact release commit before announcement.

## One-line description

An independent, human-governed automation engine for the AI-DLC v2 methodology.

## Short description

AI-DLC v2 Engine turns a pinned public methodology catalog into deterministic
workflow state, artifact guards, reviewer loops, human gates, adaptive
composition, Unit/Bolt controls, learning records, recovery, and a
tamper-evident local audit trail.

## Suggested announcement

We are publishing AI-DLC v2 Engine 0.1.0 as an open-source evaluation project.
It implements the official public AI-DLC `v2` framework version 2.6.124
through an original dependency-free Python control plane.

The repository includes the exact 33-stage and 11-core-scope catalog, a synthetic
bugfix demo, strict JSON schemas, walking-skeleton autonomy and failure
controls, complete local audit verification, security and provenance
documentation, and verified release packaging.

It is not an official AWS distribution, does not call a model, and does not
merge, deploy, or release software. Identity is asserted and the local alpha
is not production ready.

## Demo script

1. Run `aidlc-v2 catalog` and show the phase/scope counts.
2. Route a security-patch and an ambiguous multi-scope description.
3. Run the 66-event synthetic bugfix demo.
4. Show its zero-Unit incremental path and six human gates.
5. Show reviewer READY records.
6. Show an agent release request fail closed.
7. Verify the complete audit chain.
8. End with requirements provenance and production blockers.

## Supportable claims

- Independent implementation pinned to public AI-DLC Workflows v2 framework
  version 2.6.124.
- Five phases, 33 stages, 11 exact core scope grids.
- No runtime Python dependencies.
- Human authority over gates, navigation, autonomy, failures, and learning.
- Stage-major per-Unit Construction with walking-skeleton gating.
- Deterministic demo and test values.
- Recoverable atomic local state/event transactions.
- Tamper-evident hash chain for the stored event sequence.
- Offline project site with no telemetry or remote active assets.

## Claims to avoid

- Official AWS implementation or endorsement.
- Production ready, enterprise ready, highly available, or scalable.
- Autonomous software delivery.
- Authenticated or cryptographically proven humans/reviewers.
- Immutable, unhackable, zero trust, certified, or compliant.
- Trusted artifact or workspace-change verification.
- Exact compatibility with upstream internal harness formats.

## Assets

- Repository: `https://github.com/hk-775/aidlc-v2-engine`
- Project site: `https://hk-775.github.io/aidlc-v2-engine/`
- Requirements: `docs/V2_REQUIREMENTS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Logo and icon: `site/assets/`
- Editable diagram: `site/assets/architecture.drawio`
- Target AWS services diagram:
  `site/assets/aws-services-architecture.drawio` and
  `site/assets/aws-services-architecture.png`
- Publication inventory: `docs/PUBLICATION_ARTIFACTS.md`

## Pre-publication checks

- Confirm private vulnerability reporting.
- Confirm branch rules, ownership, topics, and Pages settings.
- Review Apache-2.0 and MIT-0 notices.
- Run `make test coverage scan history-scan demo package-check`.
- Review site and announcement claims against the current implementation.
- Record the exact release commit and archive SHA-256 digests.
