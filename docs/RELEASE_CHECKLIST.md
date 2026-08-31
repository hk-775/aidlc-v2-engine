# Release checklist

This checklist coordinates a source release. Completing it does not make
AI-DLC v2 Engine production ready.

## Scope and governance

- [ ] Version and release scope are documented.
- [ ] Changelog entries match implemented behavior.
- [ ] Two maintainers approved safety, schema, governance, or dependency
      changes.
- [ ] A security reviewer approved the release.
- [ ] Open blocking issues are resolved or explicitly defer the release.
- [ ] Conflicts of interest are disclosed.

## Provenance and licensing

- [ ] Clean-room provenance record is current.
- [ ] Denylist scan passes.
- [ ] Every contribution has a known compatible origin.
- [ ] License, notice, and third-party notices are reviewed.
- [ ] No personal, customer, confidential, or production material is present.
- [ ] Synthetic examples remain industry-neutral.

## Implementation

- [ ] Lifecycle and high-impact gates match documentation.
- [ ] Hard-denied agent operations fail in policy, service, and CLI tests.
- [ ] Stored schema version and migration implications are reviewed.
- [ ] Error codes and CLI output changes are documented.
- [ ] No runtime dependency was added without approval.

## Validation

- [ ] Tests pass on Python 3.11, 3.12, and 3.13.
- [ ] Branch coverage is recorded and reviewed.
- [ ] Repository scans pass.
- [ ] Credential scan passes.
- [ ] Reachable Git history scan passes.
- [ ] Workflow actions are pinned to full commit identifiers.
- [ ] Build and coverage tools install from the reviewed hash lock.
- [ ] gitleaks runs successfully, or unavailability is disclosed.
- [ ] Synthetic demo reaches expected counts and valid audit state.
- [ ] Package source and wheel build in temporary storage.
- [ ] Package contents are inspected.
- [ ] No generated archive, local state, or coverage output remains.

## Security and operations

- [ ] Threat model and adversarial review reflect current behavior.
- [ ] Security reporting channel is configured and tested.
- [ ] Production-readiness ledger is honest and current.
- [ ] No unresolved high-severity vulnerability is known.
- [ ] Local runbook recovery steps were exercised.
- [ ] Static-site content policy and external-asset scan pass.
- [ ] Manual keyboard and basic screen-reader review is complete.

## Branding and publication

- [ ] White-label checklist is complete.
- [ ] Repository URLs, owners, and reporting contacts are configured.
- [ ] Logo and icon render at intended sizes.
- [ ] Landing page and architecture explorer match the current implementation.
- [ ] Architecture downloads open from the published Pages artifact.
- [ ] Launch copy avoids unsupported claims.
- [ ] Pages deployment is manually started from `main`.
- [ ] The `github-pages` environment has required reviewers before launch.
- [ ] Release tag is annotated and matches both package version declarations.
- [ ] Release workflow produces exactly one source archive and one wheel.
- [ ] Tag, source archive, and package digests are recorded.
- [ ] Published artifacts are signed if the release process supports signing.

## Post-release

- [ ] `uv tool install` and the quickstart are tested from the published source.
- [ ] Release notes link to limitations and security reporting.
- [ ] Known issues are opened and labeled.
- [ ] Next version and support expectations are communicated.
