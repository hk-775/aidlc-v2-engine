# Configuration

AI-DLC v2 Engine has two configuration layers:

1. the pinned methodology catalog; and
2. a local safety policy.

## Methodology catalog

`stage-catalog.json` and `scope-grid.json` are package resources pinned to the
official upstream `v2` branch at framework version 2.6.124 and commit
`82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d`. They define stage order, agents, artifacts,
dependencies, reviewers, sensors, per-Unit stages, scope decisions, depth, and
test strategy.

They are not runtime-editable policy files. Changing them is a source change
that requires catalog tests, provenance review, and a new release.

Inspect the active catalog:

```console
aidlc-v2 catalog
```

## Scope, depth, and test strategy

Initialization accepts:

```console
aidlc-v2 --store .tmp/example init \
  --name "Example" \
  --description "Add notification preferences" \
  --workspace-kind greenfield \
  --scope feature \
  --depth standard \
  --test-strategy standard \
  --actor-id human_owner \
  --actor-kind human
```

`--scope auto` applies deterministic routing. Short no-keyword descriptions
use `classic`; ambiguous or rich freeform routing fails and requires an
explicit human composition choice.

Depth and test strategy can later change independently with human-only
commands:

```console
aidlc-v2 --store .tmp/example set-depth \
  --actor-id human_owner --actor-kind human \
  --depth comprehensive

aidlc-v2 --store .tmp/example set-test-strategy \
  --actor-id human_owner --actor-kind human \
  --test-strategy standard
```

## Adaptive composition

Pending ahead-of-cursor stages can be added or skipped:

```console
aidlc-v2 --store .tmp/example recompose \
  --actor-id human_owner --actor-kind human \
  --add ci-pipeline \
  --skip market-research \
  --reason "Internal feature with mandatory CI work"
```

Recomposition is rejected for Initialization, current/completed/behind-cursor
stages, the walking-skeleton anchor, and autonomous Construction.

## Policy file

Pass a policy at initialization:

```console
aidlc-v2 --store .tmp/example init \
  --name "Strict example" \
  --description "Fix a synthetic bug" \
  --workspace-kind brownfield \
  --scope bugfix \
  --policy examples/policy.strict.json \
  --actor-id human_owner \
  --actor-kind human
```

Validate without changing state:

```console
aidlc-v2 validate-policy --file examples/policy.strict.json
```

The complete shape is in `schemas/policy.schema.json`.

## Gate controls

Configurable values:

- revision limit;
- reviewer iteration cap;
- whether accept-as-is is available after the limit;
- whether complete sensor evidence is mandatory.

Mandatory invariants:

- human gates for the gated non-initialization path;
- independent approval;
- declared output checks; and
- required upstream input checks.

Policy validation rejects attempts to disable mandatory invariants.

## Agent permissions

Policy may enable or disable bounded proposal/work capabilities:

- artifact registration;
- question answers;
- sensor and reviewer records;
- gate requests;
- stage-major Unit settlement;
- autonomous Construction completion;
- Unit creation;
- Bolt failure reporting; and
- learning proposals.

The following are fixed false for agents:

- gate approval/rejection and accept-as-is;
- recomposition, skip, jump, and redo;
- depth/test/autonomy changes;
- Bolt failure resolution;
- learning promotion;
- park/resume and workflow loops;
- merge, deployment, release, risk acceptance, and gate bypass.

## Construction controls

The first Construction-stage gate and halt-on-failure behavior are mandatory.
Policy can:

- allow or disallow parallel independent Bolt scheduling metadata; and
- set the maximum Unit count.

The engine walks each Construction stage across dependency-ready Units and
opens one aggregate stage gate. Scopes without Units run at stage level. The
parallel flag preserves the methodology decision, but this implementation does
not launch upstream batch waves or worktree swarms.

## Artifact controls

SHA-256 is the only accepted digest algorithm. Code Generation must retain the
workspace-change guard.

The CLI’s `--workspace-change` flag is an assertion from the embedding
environment. A production adapter should replace it with trusted source-control
or filesystem evidence.

## Learning controls

Kept rules are effective only in a later workflow. Organization-level
promotion is not supported. A human may retain a candidate at project or team
scope; open questions cannot become rules.

## Collection limits

Policy limits artifacts, gates, questions, sensors, reviews, learnings, and
Units. Limits bound state growth but do not provide storage quotas or
performance guarantees.

## Policy immutability

`policy.json` is written at initialization and its canonical digest is bound
to every state. Editing the file directly causes integrity verification to
fail. Version 0.1.0 does not implement an audited policy-change command.
