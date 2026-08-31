# Architecture

## System boundary

AI-DLC v2 Engine is a local control plane. It records and validates methodology
state; it does not invoke models, edit source, merge changes, provision cloud
resources, deploy software, or release artifacts.

```text
human or agent caller
        |
        v
JSON CLI (`aidlc-v2`)
        |
        v
workflow service
  | catalog + scope grid
  | fail-closed policy
  | state and authority validation
        |
        v
local repository transaction
  | POSIX lock
  | complete audit verification
  | pending event/state pair
  | exclusive audit append
  | atomic state replacement
        |
        +--> state.json
        +--> policy.json
        +--> audit/*.json
```

## Components

| Component | Responsibility |
| --- | --- |
| `catalog.py` | Load and validate the pinned 33-stage and 11-core-scope methodology data |
| `models.py` | Actor, identifier, locator, and complete state validation |
| `policy.py` | Configurable limits plus non-disableable safety invariants |
| `service.py` | Stage, gate, artifact, reviewer, navigation, Bolt, and learning operations |
| `persistence.py` | Locking, recovery, verified reads, and atomic state/event commits |
| `audit.py` | Canonical serialization, state digests, event hashes, and chain verification |
| `cli.py` | Stable JSON command interface and asserted actor construction |
| `demo.py` | Deterministic synthetic end-to-end workflow |

## Catalog model

The package resources contain:

- stage order, phase, mode, lead/support agents;
- declared outputs and upstream inputs;
- stage prerequisites and sensors;
- reviewer and per-Unit metadata;
- exact execute/skip decisions for 11 core scopes; and
- default depth and test strategy.

`catalog.py` validates stage uniqueness, phase order, agent references, stage
coverage, scope coverage, reviewer metadata, and contextual artifact
producers at import time.

## Workflow state

One `state.json` contains:

- project identity and greenfield/brownfield classification;
- workflow status, scope source, depth, test strategy, iteration, cursor,
  autonomy, composition revision, and failure envelope;
- phase and stage records;
- artifact, gate, question, sensor, review, Unit, and learning collections;
- revision and audit head.

Initialization stages are completed atomically with the first state. The first
active non-initialization stage is selected from the scope plan.

## Stage and gate flow

```text
pending -> active -> awaiting_approval -> completed
                    |
                    v
                  revising
                    |
                    +----> awaiting_approval
```

Before opening or approving a gate, the service rechecks:

- every required output for the current stage and Unit kind;
- every required upstream input whose producer is active;
- the Code Generation workspace-change assertion;
- Unit presence at Units Generation;
- reviewer READY status or exhaustion of the bounded reviewer loop; and
- sensor evidence when strict sensor enforcement is enabled.

The approver must be human and distinct from the gate requester. The approval
invocation itself is treated as the fresh human turn. Rejection increments the
stage revision count. Accept-as-is becomes available only after the configured
revision limit and does not bypass artifact guards.

## Construction execution

Functional Design through Code Generation are per-Unit stages. Unit records
carry their own stage statuses and dependency list.

The current-v2 default is stage-major:

1. run the active Construction stage for every dependency-ready Unit;
2. settle each Unit only after its outputs, inputs, sensors, and reviewer
   evidence pass;
3. open one aggregate human gate for the whole stage;
4. after the first Construction-stage gate, pause once for the
   walking-skeleton autonomy choice;
5. `gated` preserves later Construction stage gates, while `autonomous`
   completes them after the same evidence guards; and
6. any Unit failure blocks ordinary progress until a human retries, skips an
   eligible non-skeleton Unit, or aborts.

Scopes without a Unit DAG execute declared per-Unit stages once at stage level;
the engine does not create a synthetic Unit. Build and Test and CI Pipeline run
globally after the per-Unit stage set. This implementation walks dependency
waves sequentially and does not launch the upstream worktree swarm.

## Navigation and composition

Human-only controls can:

- change depth or test strategy;
- add or skip pending ahead-of-cursor stages;
- skip the current Ideation/Inception stage;
- jump to a later stage with an audited reason;
- redo the current context;
- park and resume; and
- loop a completed workflow into another iteration.

Recomposition cannot change Initialization, completed work, in-progress work,
behind-cursor work, or the first executable Construction anchor. It is also
blocked during autonomous Construction.

## Transaction protocol

Every mutation runs under the project lock:

1. recover a valid pending transaction if one exists;
2. read and validate state and policy;
3. verify every audit event and the final state digest;
4. apply the operation to an in-memory copy;
5. validate the resulting state;
6. build the next hash-linked event;
7. write `.aidlc-v2.pending.json` with the event/state pair;
8. exclusively create the event file;
9. atomically replace `state.json`;
10. verify the complete chain; and
11. remove the pending marker.

If an operation raises before the pending pair is written, no revision or audit
count advances. Recovery is idempotent when an event or state write completed
before interruption.

## Audit guarantees

Each event binds:

- sequence and identifier;
- timestamp and asserted actor;
- project and resulting state revision;
- resulting state digest;
- event payload;
- previous event hash; and
- its own canonical hash.

This detects local history modification but does not prove actor identity or
resist an administrator who can replace the entire store. Production use
would need authenticated identity, signed events, external anchoring, backup,
retention, and a transactional multi-user store.

## Determinism

Production calls use current UTC time and random identifiers. Tests and the
demo inject a seed and base time. The same ordered operations then produce
byte-identical state and audit content.

## Portability and scale

The runtime has no third-party dependencies. `fcntl` locking limits the current
implementation to POSIX hosts. Every read verifies the complete audit chain,
so operation cost grows linearly with event count. That is intentional for an
inspectable alpha, not a distributed-scale design.
