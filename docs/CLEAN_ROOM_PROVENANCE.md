# Clean-room provenance

## Purpose

This record separates public methodology requirements from the original
implementation in this repository.

## Upstream requirements source

Requirements were reviewed from the public `awslabs/aidlc-workflows`
repository’s official `v2` branch at framework version 2.6.124, commit
`82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d`, licensed under MIT-0.
Framework versions in that project are not published in lockstep with Git
tags, so the exact commit—not the older highest tag—is the reproducible
baseline reviewed on 2026-08-31.

The review covered public guide/reference documents, stage definitions, scope
definitions, compiled stage/scope data, package metadata, and the upstream
license. The baseline and interpreted requirements are recorded in
[`V2_REQUIREMENTS.md`](V2_REQUIREMENTS.md).

## Bounded derived data

Two package resources were mechanically reduced from the pinned public
catalog:

- `src/aidlc_v2_engine/data/stage-catalog.json`
- `src/aidlc_v2_engine/data/scope-grid.json`

They retain only methodology facts needed for deterministic execution:
identifiers, ordering, phases, agent assignments, declared artifacts,
dependencies, sensors, reviewer metadata, per-Unit markers, scope decisions,
and scope defaults. Both files embed the upstream repository, branch,
framework version, commit, and review date.

The derived data is distributed under the upstream MIT-0 permission identified
in [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Original implementation

No upstream TypeScript engine, harness adapter, hook, test, generated
distribution, prose page, diagram, branding asset, or model configuration was
copied into this project.

The following are original Apache-2.0 project work:

- Python catalog loader and validation;
- policy and authority model;
- workflow and Bolt state machine;
- artifact, reviewer, gate, learning, and sensor operations;
- atomic JSON repository and hash-chained audit implementation;
- CLI and deterministic demo;
- tests, schemas, security tooling, documentation, site, and release process.

The existing first-generation AI-DLC Engine repository was used only as a
local engineering and open-source artifact skeleton. Its Git history was not
copied. Its durable persistence design was adapted within the same
contributor-controlled code lineage, while the old six-stage lifecycle,
policy, CLI, tests, schemas, and public claims were replaced.

## Independence boundary

This repository does not claim compatibility with upstream internal file
formats, TypeScript utilities, harness hooks, generated `dist/` trees, model
configuration, or exact audit taxonomy. It implements methodology semantics
through a separate standard-library Python control plane.

## Synthetic-data requirement

Examples, tests, screenshots, and demos must use synthetic data. Contributions
must not include customer material, credentials, private source, personal
records, internal endpoints, or production artifacts.

## Contributor obligations

Contributors must:

1. identify the source and license of non-original material;
2. update third-party notices when derived or copied material changes;
3. avoid submitting material without clear reuse rights;
4. preserve the exact upstream branch/commit baseline when changing catalog data;
5. explain intentional deviations from the pinned methodology; and
6. run source, credential, provenance, history, package, and demo checks.

This record documents engineering process, not legal advice.
