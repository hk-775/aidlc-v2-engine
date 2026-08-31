# Threat model

## Scope

The model covers the local CLI, catalog, policy, workflow service, JSON state,
pending transaction, and audit directory on one POSIX host.

## Assets

- Correct methodology cursor, stage plan, depth, and test strategy.
- Human gate and reviewer decisions.
- Artifact metadata and Unit/Bolt state.
- Learning decisions and sensor records.
- Policy binding and audit integrity.
- Availability and provenance of the local store.

## Actors and assumptions

- Human and agent callers present asserted identifiers.
- Cooperative writers use the project lock.
- The evaluator protects the host account.
- Python, the kernel, and local filesystem provide expected semantics.

Identity truth is not verified. This is the largest alpha trust assumption.

## Threats and controls

### Agent claims human authority

Controls:

- actor-kind checks on every human-only operation;
- governance roles rejected for agent actors;
- hard-denied agent operation set;
- policy schema constants; and
- no external merge/deploy/release implementation.

Residual risk: an embedding environment can falsely label an agent as human.

### Self-approval or stale gate

Controls:

- gate requester cannot approve or reject the same gate;
- gate must match the live stage and Unit;
- resolved gates cannot be reused;
- redo, skip, and jump supersede pending gates; and
- approval rechecks all stage guards.

Residual risk: two asserted identifiers may represent one real person.

### Evidence bypass

Controls:

- artifacts must be declared by the current stage;
- required outputs are checked by Unit kind;
- required active-producer inputs are checked;
- evidence identifiers must belong to the current context;
- SHA-256 format and safe relative locators are validated;
- Code Generation requires workspace-change evidence.

Residual risk: artifact bytes are external and are not re-read. The
workspace-change flag is asserted, not independently proven.

### Reviewer impersonation or memory contamination

Controls:

- agent reviewer identifier must match catalog metadata;
- review record is independent of gate requester authority;
- iteration count is bounded; and
- the human remains final decision-maker.

Residual risk: reviewer inputs and source context are supplied by the embedding
environment and could be incomplete.

### Unsafe autonomous Construction

Controls:

- the first ordered Unit is designated as the walking skeleton;
- autonomy is selected once by a human after the first aggregate Construction
  stage gate;
- autonomous completion is restricted to later Construction stages;
- normal evidence and reviewer checks still apply;
- any failure halts ordinary mutations;
- human retry/skip/abort is required;
- the walking-skeleton Unit cannot be skipped; and
- autonomous Construction cannot park or recompose.

Residual risk: the engine records control-plane state but does not sandbox an
external worker that performs source changes.

### Plan manipulation

Controls:

- only humans can recompose, skip, jump, or redo;
- Initialization, completed/current/behind-cursor work is frozen;
- walking-skeleton anchor cannot move during recomposition;
- all changes and reasons are audited.

Residual risk: a careless authorized human can choose an unsafe plan.

### Learning escalation

Controls:

- learning begins as a candidate;
- only a human can keep it;
- target is project or team, never organization;
- open questions cannot become rules; and
- kept learning is marked effective only next workflow.

Residual risk: no semantic conflict detector or external rule compiler is
implemented.

### Policy weakening

Controls:

- exact-key policy validation;
- human/independence/evidence invariants fixed true;
- first-Bolt gate and halt-on-failure fixed true;
- dangerous agent permissions fixed false;
- Code Generation guard fixed true;
- policy digest bound to state.

Residual risk: modified source can change invariants. Release signatures and
provenance attestations are not yet provided.

### Audit tampering

Controls:

- exclusive event creation;
- owner-read-only event mode;
- contiguous filename and sequence checks;
- canonical event hashes and previous-hash links;
- final state digest binding;
- full verification before reads and writes.

Residual risk: a privileged attacker can replace state, policy, and the entire
history consistently. No signature or external anchor exists.

### Interrupted or concurrent write

Controls:

- POSIX exclusive advisory lock;
- pending event/state pair;
- file and directory flushes;
- idempotent event append;
- atomic state replacement;
- fail-closed recovery validation.

Residual risk: non-cooperating processes, network filesystems, or storage
failures can violate assumptions. Crash/fault certification is incomplete.

### Path abuse

Controls:

- symbolic links rejected for key storage paths;
- no-follow flags where available;
- owner-only directory permissions;
- normalized relative artifact locators;
- artifact locators are never opened by the engine.

Residual risk: callers can choose any root their account can write.

### Secret or personal-data exposure

Controls:

- synthetic fixtures and warnings;
- repository credential/provenance scans;
- no network integration or telemetry;
- bounded input lengths.

Residual risk: users can enter secrets or sensitive prose into stored fields.
There is no classifier, redaction system, or encryption.

### Denial of service

Controls:

- collection and input limits;
- single local writer;
- deterministic validation.

Residual risk: every operation verifies the full history and state collections
can still be large.

## Out of scope

- compromised runtime, kernel, or host administrator;
- external worker sandboxing;
- social engineering;
- cloud or deployment-system authorization;
- legal, privacy, or regulatory sufficiency.

See [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md) for blocking work.
