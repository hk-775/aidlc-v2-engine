# AI-DLC v2 requirements baseline

## Source and pin

This implementation was derived from public methodology requirements in:

- repository: `awslabs/aidlc-workflows`
- branch: `v2`
- framework version: `2.6.124`
- commit: `82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d`
- upstream license: MIT-0
- baseline reviewed: 2026-08-31

Upstream framework versions are carried in the committed `v2` tree and are not
kept in lockstep with GitHub tags or releases. The highest Git tag at the
review date was older than the active GA framework, so this implementation
pins the authoritative branch to the exact commit above. A later branch
revision requires another reviewed catalog update.

The bounded stage and scope data in
`src/aidlc_v2_engine/data/` records the exact pinned identifiers and mappings.
Engine logic, persistence, tests, CLI, documentation, and project branding are
independent implementations.

## Methodology shape

| Phase | Stages |
| --- | --- |
| Initialization | workspace-scaffold, workspace-detection, state-init |
| Ideation | intent-capture through approval-handoff |
| Inception | reverse-engineering through delivery-planning |
| Construction | functional-design through ci-pipeline |
| Operation | deployment-pipeline through feedback-optimization |

The catalog contains five phases and 33 stages. Inception contains
`domain-design` at 2.6, `units-generation` at 2.7, the new
`contract-design` stage at 2.8, and `delivery-planning` at 2.9.
Initialization is automatic;
all other gated-path stages require human approval. Phase boundaries verify
artifact presence and workflow consistency.

## Scope presets

| Scope | Active / total | Default depth | Default tests |
| --- | ---: | --- | --- |
| enterprise | 33 / 33 | comprehensive | comprehensive |
| feature | 33 / 33 | standard | standard |
| mvp | 23 / 33 | standard | standard |
| poc | 8 / 33 | minimal | minimal |
| bugfix | 9 / 33 | minimal | minimal |
| refactor | 10 / 33 | minimal | minimal |
| infra | 13 / 33 | standard | standard |
| security-patch | 10 / 33 | minimal | minimal |
| classic | 26 / 33 | standard | standard |
| workshop | 26 / 33 | standard | minimal |
| express | 10 / 33 | minimal | minimal |

Depth controls artifact detail. Test strategy independently controls test
volume and test types. Both can change during a workflow through a human
decision.

Deterministic routing recognizes bugfix, refactor, infrastructure,
security-patch, proof-of-concept, MVP, workshop, and express vocabulary.
`classic` is the underlying no-keyword default. Multiple matches, rich
freeform intent, or a specialized keyword buried in a description longer than
five words require adaptive composition rather than silently selecting a
full-feature scope.

## Stage execution requirements

- Stage states: pending, active, awaiting approval, revising, completed,
  skipped.
- Happy path: pending → active → awaiting approval → completed.
- Rejection path: awaiting approval → revising → awaiting approval.
- After three revisions, a human may accept the work as-is; artifact guards
  still apply.
- Guide Me, Edit File, and Chat interactions converge on canonical recorded
  answers.
- The topology is 29 inline stages, two subagent stages, one pipeline, and one
  mob: Reverse Engineering is the pipeline, Practices Discovery and Code
  Generation use subagents, and User Stories uses the mob topology.
- Stage outputs use lowercase kebab-case canonical identifiers.
- Most artifact identifiers have one producer; `traceability` is intentionally
  emitted by several stages and is resolved in stage context.
- Required inputs apply when their producer is active in the selected plan.
- Code Generation must include evidence of real workspace work, not only
  documentation.

## Agent and reviewer requirements

Eleven domain agents are declared:

1. product
2. design
3. delivery
4. architect
5. AWS platform
6. compliance
7. DevSecOps
8. developer
9. quality
10. pipeline/deploy
11. operations

Product-lead and architecture reviewer agents provide independent READY or
NOT-READY verdicts. Reviewer loops are bounded to two iterations by default.
Reviewer classes are advisory in Ideation/Inception and adversarial in the
per-Unit Construction design/code stages, subject to each scope’s review cap.
`express` disables reviewer dispatch. Reviewer advice never replaces final
human judgment. A composer agent proposes stage-plan changes; only a human may
approve a live recomposition.

## Construction and Bolt requirements

- Functional Design through Code Generation are declared per Unit of Work.
- Build and Test and CI Pipeline run once after the Unit/Bolt set.
- Unit kinds: service, spec, UI, packaging, and library.
- Required per-Unit outputs may be pruned by Unit kind.
- The default Construction walk is stage-major: run one stage for every Unit,
  open one stage-level gate, then advance to the next stage.
- `bolt-plan.md` is planning input; runtime Unit ordering comes from the Unit
  dependency DAG.
- The first in-scope Construction-stage gate is the walking-skeleton gate.
- After that gate, a human selects `autonomous` or `gated` once. Autonomous
  mode skips the remaining Construction completion gates while retaining
  evidence, reviewer, and failure guards.
- Scopes that skip Units Generation use a zero-Unit stage-level execution path;
  they do not receive an invented synthetic Unit or walking-skeleton ceremony.
- Dependency-independent Units may form waves, and Code Generation may fan out
  through a worktree swarm in the upstream harness.
- Any failure halts and requires a human retry, skip, or abort choice.
- The walking skeleton cannot be skipped after failure.

## Navigation, state, and recovery requirements

- Scope, depth, test strategy, execute/skip plan, workspace classification,
  cursor, revisions, Units, autonomy, and recovery markers persist.
- Resume supports continuing the checkpoint, redoing current work, jumping,
  or starting another iteration.
- Pending ahead-of-cursor stages may be recomposed.
- Completed, in-progress, behind-cursor, and walking-skeleton anchor decisions
  remain frozen.
- Autonomous Construction cannot be parked or recomposed.
- Operation may complete the workflow or loop back for another lifecycle
  iteration.

## Knowledge, learning, and sensors

- Knowledge resolves additively from organization to team, project, phase, and
  stage.
- Interpretations, deviations, tradeoffs, and open questions form the memory
  diary.
- Human-kept learning may target project or team scope.
- Learned rules become effective in a later workflow, not mid-run.
- Open questions do not become rules.
- Required-sections, upstream-coverage, linter, and type-check sensors are
  deterministic advisory checks.

This engine records rule-learning and sensor outcomes. It does not execute
arbitrary rule or sensor plugins.

## Audit requirements and implementation choice

The pinned upstream README describes a 91-event audit taxonomy. This engine
does not claim byte-for-byte event taxonomy compatibility.

It implements the load-bearing event families—workflow, phase/stage, gate,
navigation, artifact, question, reviewer, sensor, Bolt, autonomy, learning,
failure, and recovery—using canonical JSON events. Events are sequence-numbered,
exclusively created, previous-hash linked, and bound to the resulting state
digest. A recoverable pending transaction keeps event and state commitment
atomic on the local filesystem.

## Upstream implementation details not adopted

The official release uses Bun, TypeScript, generated harness distributions,
and adapters for multiple coding assistants, with AWS Bedrock settings in its
shipped harness configuration.

Those are implementation choices rather than methodology invariants. This
project instead provides a standard-library Python control plane with no
runtime dependency, model invocation, cloud credential, or harness
requirement.

## Coverage status

| Requirement group | Status in 0.1.0 |
| --- | --- |
| 33-stage catalog, 11 core scopes, depth, test strategy | Implemented |
| Artifact/input guards and human gates | Implemented |
| Reviewer loop and tri-mode records | Implemented |
| Recompose, skip, jump, redo, park/resume | Implemented |
| Stage-major Units, zero-Unit paths, walking skeleton, autonomy, failure envelope | Implemented |
| Learning candidates and advisory sensor records | Implemented |
| Hash-chained audit and local recovery | Implemented |
| Harness adapters and model invocation | Not in scope |
| Worktree swarm, parallel wave dispatch, and team Unit ownership | Deferred |
| Plugin installation and dynamic plugin scopes | Deferred |
| Spaces, multi-repository coordination, DocumentKB, and three-role ensembles | Deferred |
| Automatic rule compiler and sensor execution | Deferred |
| Authenticated identity and distributed service | Deferred |
