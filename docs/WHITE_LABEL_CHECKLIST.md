# White-label checklist

Complete this checklist before adapting or publishing AI-DLC v2 Engine under a
different project or organization identity.

## Ownership and contacts

- [ ] Configure project URLs after the new repository location is final.
- [ ] Configure the repository owner and maintainer team in `CODEOWNERS`.
- [ ] Configure private security and conduct reporting channels.
- [ ] Name release stewards and security reviewers.
- [ ] Review copyright ownership and contributor agreements.

## Name and visual identity

- [ ] Confirm the new name and abbreviation are available for intended use.
- [ ] Replace name references in package metadata, CLI help, site, schemas,
      docs, notices, and workflows.
- [ ] Replace or deliberately retain the logo and icon under the license.
- [ ] Update SVG titles, descriptions, filenames, and accessible alt text.
- [ ] Update architecture explorer copy, canonical URLs, and downloadable assets.
- [ ] Update colors only after checking contrast and focus visibility.

## Product truthfulness

- [ ] Rewrite positioning for actual implemented behavior.
- [ ] Keep alpha, beta, or production status evidence-based.
- [ ] Remove unsupported scale, security, compliance, and integration claims.
- [ ] Distinguish workflow completion from external merge, deployment, or
      release execution.
- [ ] Update the production-readiness ledger.

## Technical identity

- [ ] Choose a package name and console script that do not collide.
- [ ] Update deterministic demo seeds if identity-sensitive output should
      change.
- [ ] Update schema identifiers while preserving version compatibility.
- [ ] Decide whether existing state remains readable.
- [ ] Add a migration plan before changing stored fields.

## Policies and governance

- [ ] Preserve hard agent restrictions or document a fork with a different
      risk model.
- [ ] Map human roles to the operator's authenticated identity system.
- [ ] Review gate names and evidence types for industry neutrality.
- [ ] Update governance voting and approval rules.
- [ ] Update support scope and service expectations.

## Legal and provenance

- [ ] Preserve Apache License 2.0 requirements.
- [ ] Update `NOTICE` without removing required attributions.
- [ ] Update third-party notices for every new dependency and asset.
- [ ] Keep the clean-room provenance record or replace it with an equally clear
      process record.
- [ ] Run the encoded provenance denylist scan.
- [ ] Obtain qualified legal review when needed.

## Publication

- [ ] Run tests, coverage, scans, demo, and package inspection.
- [ ] Run the full release checklist.
- [ ] Review static-site links, content policy, accessibility, and metadata.
- [ ] Review both the landing page and architecture explorer with scripts on
      and off.
- [ ] Keep Pages deployment manual, constrained to `main`, and protected by
      environment reviewers.
- [ ] Remove local state, temporary output, coverage data, and archives.
- [ ] Inspect the final source archive before publishing.
