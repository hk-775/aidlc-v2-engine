# Security policy

## Supported versions

AI-DLC v2 Engine has not yet published a supported production release. The
current `0.1.x` line is an alpha evaluation candidate. Security fixes are
applied to the latest source revision when maintainers can reproduce and safely
address the issue.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose data, bypass a
human gate, corrupt the audit sequence, escape a storage boundary, or grant
agent authority.

Use GitHub's
[private vulnerability reporting form](https://github.com/hk-775/aidlc-v2-engine/security/advisories/new).
If GitHub reports that the form is unavailable, do not open a public issue.
Contact the repository steward through a previously verified private channel.
Public repository launch requires private vulnerability reporting to be
enabled and tested.

A useful report includes:

- affected version or revision;
- environment and exact command;
- expected and observed behavior;
- minimal synthetic reproduction;
- security impact and assumptions; and
- whether any real data or credential was involved.

Never include secrets, personal records, customer material, or exploit data
that is unnecessary to reproduce the issue.

## Response targets

These are process goals, not service-level guarantees:

- acknowledge a complete private report within five working days;
- provide an initial severity and reproduction assessment within ten working
  days; and
- coordinate disclosure timing with the reporter after a fix or documented
  mitigation exists.

## Security boundary

The alpha implementation:

- accepts caller identity and roles from the local invocation;
- stores local JSON without encryption;
- uses advisory file locking and atomic replacement;
- creates audit event files exclusively and verifies a SHA-256 hash chain;
- never executes merge, deployment, release, or gate-bypass operations; and
- makes no network requests.

It does not provide authentication, cryptographic actor signatures,
non-repudiation, host hardening, malware isolation, encrypted storage, remote
authorization, multi-host consensus, or recovery from a fully compromised
administrator.

## Safe evaluation

- Use synthetic, non-sensitive content.
- Place the store in a user-owned directory. AI-DLC v2 Engine normalizes the
  project and audit directories to owner-only permissions but does not harden
  ancestors.
- Do not run the CLI with elevated privileges.
- Verify the audit chain before and after an evaluation.
- Keep external execution systems disconnected.
- Review policy and actor roles rather than trusting demo defaults.

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) and
[docs/ADVERSARIAL_REVIEW.md](docs/ADVERSARIAL_REVIEW.md).
