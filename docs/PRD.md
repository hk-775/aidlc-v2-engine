# Product requirements

## Product

AI-DLC v2 Engine is a dependency-free Python control plane that makes the
public AI-DLC v2 methodology inspectable, deterministic, testable, and locally
auditable without bundling a model or coding-assistant harness.

## Users

- engineers evaluating AI-DLC v2 workflow semantics;
- platform teams designing a governed agent harness;
- security and risk reviewers testing authority boundaries;
- educators demonstrating scope and Bolt behavior; and
- open-source contributors studying a small reference control plane.

## Goals

1. Pin one authoritative v2 baseline.
2. Represent all phases, stages, scopes, defaults, agents, artifacts, and
   reviewer metadata.
3. Enforce human authority for gates and workflow-shaping decisions.
4. Guard stage completion with declared evidence and upstream inputs.
5. Model stage-major per-Unit Construction, zero-Unit incremental paths,
   walking-skeleton gating, autonomy, and failure.
6. Preserve deterministic recovery and a tamper-evident audit trail.
7. Ship the implementation with complete open-source governance, security,
   provenance, documentation, test, and release artifacts.

## Non-goals

- model invocation or prompt orchestration;
- official AWS compatibility or endorsement;
- source editing, merge, deployment, or release execution;
- authenticated identity or organization role administration;
- distributed coordination or high availability;
- compliance certification; and
- byte-compatible upstream internal state or audit formats.

## Functional requirements

### Catalog and routing

- Exactly five phases, 33 stages, and 11 core scopes from the pinned baseline.
- Exact scope stage counts and depth/test defaults.
- Deterministic specialized routing.
- Ambiguity must require an explicit human choice.
- Catalog drift must fail tests.

### State and gates

- Strict schema versioning and exact-key validation.
- Automatic Initialization.
- Pending, active, awaiting approval, revising, completed, and skipped states.
- Human-only, independent approval.
- Three-strike accept-as-is escape hatch.
- Phase status derived from stage completion.

### Evidence

- Canonical artifact vocabulary with contextual producer resolution.
- Required output coverage by stage and Unit kind.
- Required upstream inputs when their producer is active.
- SHA-256 metadata, normalized relative locator, and submitter/time.
- Code Generation workspace-change assertion.

### Interaction and review

- Guide, Edit File, and Chat answer records.
- Product and architecture reviewer identity checks.
- READY/NOT-READY verdicts.
- Bounded reviewer iterations with final human authority.

### Navigation

- Human depth and test-strategy changes.
- Ahead-of-cursor recomposition.
- Early-stage skip, audited jump, redo, park/resume, and iteration loop.
- Frozen completed/current/behind-cursor work and Construction anchor.

### Construction

- Unit kinds and dependencies.
- Per-Unit stages 3.1–3.5 with a stage-major default walk.
- One aggregate gate after every Unit settles the active Construction stage.
- Zero-Unit stage-level behavior when Units Generation is skipped.
- First Construction-stage gate as the walking-skeleton checkpoint.
- One-time autonomous/gated ladder.
- Autonomous completion for later Construction stages.
- Halt-and-ask failure envelope.
- Global Build and Test and CI Pipeline after Units.

### Learning and sensors

- Memory-diary candidate sections.
- Human keep/reject decision.
- Project/team targets only.
- Next-workflow effectiveness.
- Recorded deterministic sensor outcomes.

### Persistence and audit

- Owner-only project directories.
- POSIX lock and symlink rejection.
- Full verified reads.
- Recoverable pending event/state pair.
- Exclusive immutable event creation.
- Atomic state replacement.
- Canonical state digest and previous-hash chain.

### Interface and packaging

- Stable JSON CLI.
- No runtime dependencies.
- Deterministic demo.
- JSON Schemas.
- Source/history/provenance/security scans.
- Verified source and wheel archives from annotated tags.

## Safety invariants

- Agents cannot satisfy human decisions.
- Gate requester cannot approve the same gate.
- Artifact and input guards cannot be disabled.
- First-Bolt gate and halt-on-failure cannot be disabled.
- Code Generation requires workspace-change evidence.
- Learned rules do not alter an in-flight workflow.
- Organization-level automatic learning promotion is absent.
- External delivery actions have no implementation path.

## Success criteria for 0.1.0

- Catalog tests match 33 stages and scope counts `33, 33, 23, 8, 9, 10, 13,
  10, 26, 26, 10`.
- Synthetic bugfix demo completes six active post-initialization stages.
- Demo audit verification succeeds.
- Unit tests cover happy, denial, malformed, rejection, autonomy, failure,
  recomposition, learning, and tamper paths.
- Repository and package checks pass without network access.
- Documentation clearly separates implemented behavior, limitations, and
  upstream provenance.

## Deferred questions

- Which authenticated identity and policy-administration system should embed
  the engine?
- How should trusted workspace-change evidence be collected?
- Which signed event and external checkpoint design is appropriate?
- Should a future adapter execute deterministic sensors in a sandbox?
- How should rule files be compiled and versioned across organizations?
- What migration model should support later catalog and state versions?
