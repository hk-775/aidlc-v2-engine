# Production readiness

## Statement

Version 0.1.0 is suitable for local, synthetic evaluation. It is not ready to
authorize or operate production delivery.

## Readiness ledger

| Area | Status | Current evidence | Production gap |
| --- | --- | --- | --- |
| v2 catalog | Implemented | Pinned 33-stage/11-core-scope data and drift tests | Upgrade and migration policy |
| Workflow determinism | Implemented locally | Injected IDs/times and deterministic tests | Distributed ordering |
| Artifact guards | Implemented locally | Output/input/Unit-kind/workspace checks | Trusted content retrieval |
| Human gates | Partial | Kind and requester separation | Authenticated identity and role lifecycle |
| Reviewer loop | Implemented locally | Identity, verdict, cap, tests | Trusted isolated review execution |
| Adaptive composition | Implemented locally | Frozen boundaries and audit | Organization change policy |
| Construction autonomy | Implemented locally | Stage-major Units, zero-Unit path, skeleton gate, ladder, failure envelope | Worker sandbox, parallel waves, swarm attestations |
| Plugin and multi-repo framework | Deferred | Explicitly excluded from current boundary | Dynamic plugin scopes, spaces, repositories, ensemble receipts |
| Learning | Partial | Human keep/reject and next-workflow marker | Rule conflict compiler and governance |
| Sensors | Partial | Declared advisory result records | Sandboxed execution and trusted evidence |
| Local persistence | Partial | Lock, flush, pending recovery, atomic replace | Certified database and fault testing |
| Audit integrity | Partial | Canonical hash chain and state binding | Signatures, external anchor, retention |
| Authentication | Blocked | None | Human/workload identity provider |
| Authorization administration | Blocked | CLI-asserted roles | Protected role and policy administration |
| Confidentiality | Blocked | Local permissions only | Encryption, keys, classification, redaction |
| Backup/restore | Blocked | Manual copy guidance | Tested backup, restore, rollback defense |
| Schema migration | Blocked | Version rejection only | Forward/rollback migrations |
| Remote/multi-user service | Missing | None | Authenticated API and transactional coordination |
| High availability | Missing | None | Replication, failover, recovery objectives |
| Observability | Missing | JSON errors and files | Metrics, traces, alerts, redaction |
| Performance evidence | Missing | Functional tests only | Benchmarks and capacity model |
| Supply chain | Partial | No runtime deps, pinned actions, hash-locked build, package verification | Signed artifacts, SBOM, attestations, reproducibility |
| Security testing | Partial | Denial/tamper tests and scans | Independent assessment, fuzzing, fault injection |
| Privacy/compliance | Not claimed | Synthetic defaults | Qualified context-specific review |
| Support operations | Missing | Community docs | Staffing, service levels, escalation |

## Blocking risks

1. Caller identity and human status are unauthenticated.
2. External workers are not sandboxed or attested.
3. Artifact and workspace-change evidence is caller asserted.
4. A privileged local attacker can replace a complete valid-looking history.
5. The filesystem store has no certified migration, backup, or restore path.
6. Full-chain verification and advisory locking do not scale to distributed
   operation.
7. Sensitive fields are neither encrypted nor automatically redacted.
8. No production monitoring, incident ownership, or recovery objectives exist.

## Maturation sequence

The
[target AWS services reference architecture](ARCHITECTURE.md#target-aws-services-reference-architecture)
maps these gaps to one possible deployment shape. It is planning material only:
the repository contains no AWS IaC, remote service implementation, or deployed
resources.

### Evaluation hardening

- property and fuzz tests for state/navigation;
- crash injection at every persistence boundary;
- schema compatibility and migration rules;
- benchmark representative event histories;
- manual security and accessibility review.

### Authenticated service prototype

- verified human and workload identity;
- protected policy and role administration;
- transactional database with append-only events;
- signed events and external checkpoints;
- trusted source/artifact evidence adapters;
- sandboxed worker and sensor execution.

### Operational validation

- backups, restore drills, migrations, monitoring, and incident response;
- service targets based on measured workloads;
- independent security assessment;
- non-production, low-sensitivity pilot.

### Production decision

Production use requires explicit acceptance by accountable engineering,
security, operations, privacy, legal, and business owners. Repository checks
alone are not production evidence.
