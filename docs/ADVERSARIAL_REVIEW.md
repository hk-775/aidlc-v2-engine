# Adversarial review

This is a design review, not a penetration test.

| ID | Scenario | Status | Residual work |
| --- | --- | --- | --- |
| AR-01 | Caller labels an agent as human | Open blocker | Authenticated human/workload identity |
| AR-02 | Policy enables agent approval, release, or bypass | Blocked | Protect source and policy administration |
| AR-03 | Gate requester self-approves | Blocked for typed actors | Prove real-world identity separation |
| AR-04 | Missing stage outputs are approved | Blocked | Trust artifact bytes and workspace evidence |
| AR-05 | Reviewer agent is impersonated | Blocked by asserted ID | Authenticate reviewer execution |
| AR-06 | Recomposition changes completed/current work | Blocked | Organization-specific change control |
| AR-07 | Autonomous mode skips walking skeleton | Blocked | Attest external worker execution |
| AR-08 | Bolt failure continues unattended | Blocked | Integrate worker cancellation guarantees |
| AR-09 | Open question becomes a rule | Blocked | Add semantic conflict analysis |
| AR-10 | Audit event is edited/deleted/reordered | Detected | Sign and externally anchor checkpoints |
| AR-11 | Entire state/history is rolled back consistently | Not independently detectable | External trusted checkpoint |
| AR-12 | Process dies during commit | Recoverable by design | Systematic kill/fault injection |
| AR-13 | Rogue process ignores advisory lock | Open | Transactional protected service |
| AR-14 | Symlink redirects storage | Partially mitigated | Descriptor-relative traversal tests |
| AR-15 | Sensitive prose enters local state | Open | Classification, redaction, encryption |
| AR-16 | Static site loads third-party active content | Blocked in source | Preserve hosting controls |
| AR-17 | Package omits catalog or provenance data | Blocked by package checks | Signed provenance attestations |
| AR-18 | Full history causes denial of service | Partially mitigated | Quotas, archival, benchmarks |

## Regression abuse cases

- Flip every hard-denied agent permission.
- Claim governance roles as an agent.
- Approve a gate with its requester.
- Open a gate without outputs or required inputs.
- Complete Code Generation without workspace-change evidence.
- Record a reviewer verdict under the wrong agent identity.
- Move the walking-skeleton anchor.
- Recompose or park autonomous Construction.
- Skip the walking skeleton after failure.
- Promote an open question.
- Mutate state, policy, event content, event order, count, filename, or head.
- Load a network script from the project site.
- Insert credential-shaped or prohibited provenance material.

## Conclusion

The engine meaningfully constrains correctly typed local callers and detects
accidental or partial history tampering. Authenticated identity, trusted
artifact/workspace evidence, worker sandboxing, external audit anchoring,
hardened storage, and production operations remain unresolved blockers.
