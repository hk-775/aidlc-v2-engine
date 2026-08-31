# AI-DLC v2 Engine PRFAQ

## Press release

### Independent AI-DLC v2 automation engine opens for local evaluation

AI-DLC v2 Engine turns the public AI-DLC v2 methodology into a deterministic,
human-governed Python control plane. It models 33 stages, 11 core scopes,
artifacts, reviewer loops, adaptive composition, stage-major Units, autonomy,
failure handling, learning, and recovery without bundling a model or deployment
integration.

The alpha is designed for inspection: no runtime dependencies, stable JSON
commands, strict schemas, a synthetic end-to-end demo, a recoverable local
store, and a hash-linked audit history.

## FAQ

### Is this the official AWS implementation?

No. It is an independent implementation. The methodology catalog is pinned to
the official public `awslabs/aidlc-workflows` `v2` branch at framework version
2.6.124 and commit `82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d`
under MIT-0; the engine code is original Apache-2.0 work.

### What problem does it solve?

It makes methodology control decisions explicit and testable: which stages
run, what artifacts they owe, when a reviewer is required, who can approve,
how Units advance, what autonomy means, and how failures or navigation changes
are recorded.

### Does it write code or call an AI model?

No. An external harness can use this engine as a control plane. Model
invocation, source editing, and worker execution remain outside the process.

### Can an agent approve, deploy, or release?

No. Human decisions and external delivery authority are permanently denied to
agents. The engine implements no merge, deployment, or release path.

### How does Construction autonomy work?

The default walk completes one Construction stage across every Unit, then
opens one stage-level gate. The first such gate is the walking-skeleton gate;
a human then chooses `gated` or `autonomous` once. Incremental scopes without
a Unit DAG run stage-level and skip synthetic Unit ceremony. Any Unit failure
returns control to a human.

### What does the engine store?

Project/workflow state, artifact metadata and digests, questions, reviewer and
sensor results, gates, Units, learning candidates, policy, and audit events.
It does not store artifact content.

### Is the audit log immutable?

No. It is tamper-evident. The chain detects partial modification, deletion,
insertion, or reordering. A privileged attacker who replaces the entire store
can defeat this local assurance.

### Is it production ready?

No. Identity is asserted, the store is local, evidence is not trusted, events
are unsigned, and no distributed or operational service exists.

### Why Python instead of the upstream TypeScript harness?

The goal is a small, dependency-free, harness-neutral control plane that can
be evaluated independently. It implements methodology semantics, not upstream
internal tooling.

### How can reviewers start?

Run `aidlc-v2 catalog`, the deterministic demo, the complete test/scan suite,
and then read the requirements baseline, threat model, provenance record, and
production-readiness ledger.
