# Publication artifacts

## Purpose

This inventory defines the complete customer-facing artifact set for AI-DLC
v2 Engine. It keeps the repository, project site, architecture material,
evaluator guides, and release archives aligned with the current implementation.

An artifact belongs in this set only when it can be maintained from repository
source and validated without private services or production credentials.

## Customer-facing set

| Artifact | Purpose | Canonical source |
| --- | --- | --- |
| Repository overview | Product boundary, fast evaluation, limitations, and document index | `README.md` |
| Guided evaluation | Install, demo, denied action, policy, and manual project workflow | `QUICKSTART.md` |
| Evaluator checklist | Supported environment, validation, smoke tests, and cautions | `STARTUP.md` |
| Project landing page | Public product summary and synthetic lifecycle status | `site/index.html` |
| Architecture explorer | Interactive lifecycle, governance, persistence, and trust-boundary walkthrough | `site/architecture.html` |
| Requirements baseline | Pinned upstream source, methodology requirements, implementation coverage, and deviations | `docs/V2_REQUIREMENTS.md` |
| Provenance record | Boundary between derived MIT-0 catalog data and original Apache-2.0 implementation | `docs/CLEAN_ROOM_PROVENANCE.md`, `THIRD_PARTY_NOTICES.md` |
| Synthetic evidence set | Canonical v2 output-name examples for the bugfix demo path | `examples/evidence/` |
| Long-form architecture | Components, transaction sequence, trust boundaries, and scale limits | `docs/ARCHITECTURE.md` |
| Feature inventory | Implemented lifecycle and authority flows | `docs/FEATURES_AND_FLOWS.md` |
| Readiness ledger | Implemented evidence, production gaps, and blocking risks | `docs/PRODUCTION_READINESS.md` |
| Security material | Reporting policy, threat model, adversarial review, and responsible use | `SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/ADVERSARIAL_REVIEW.md`, `docs/RESPONSIBLE_USE.md` |
| Launch copy | Supportable claims, claims to avoid, demo script, and asset locations | `launch-materials.md` |
| Release evidence | Verified source and wheel archives with recorded SHA-256 digests | `.github/workflows/release.yml`, `tools/release_check.py` |

## Visual source of truth

The architecture has several representations for different consumers:

- `site/assets/architecture.drawio` is the editable diagram source.
- `site/assets/architecture.png` is the README and presentation render.
- `site/assets/architecture.svg` is the accessible vector used on the landing
  page.
- `site/assets/architecture.dot` is the compact logical graph source.

The canonical visual identity files are:

- `site/assets/aidlc-v2-engine-logo.svg`
- `site/assets/aidlc-v2-engine-icon.svg`

The project site uses only repository-owned assets. It loads no remote fonts,
scripts, images, telemetry, or network APIs.

## Release inclusion

The source distribution must contain:

- the landing page and architecture explorer;
- both site JavaScript files and the shared stylesheet;
- the editable draw.io source and PNG render;
- this publication inventory and the long-form architecture reference; and
- the v2 requirements baseline and attributed catalog resources;
- the release verification tooling.

`tools/package_check.py` and `tools/release_check.py` enforce those members.

## Validation

Before publication or announcement, run:

```console
make test
make coverage
make scan
make history-scan
make demo
make package-check
```

Then verify both pages locally:

```console
make site
```

Open `/` and `/architecture.html` from the printed local address.

## Intentional omissions

AI-DLC v2 Engine version 0.1 does not include container images, cloud deployment
templates, production evidence bundles, service dashboards, or signed runtime
artifacts. The implementation is a local evaluation engine with no remote API
or external delivery integration, so publishing those artifacts would imply a
deployment surface that does not exist.

Runtime dependencies are empty. The build and coverage toolchain remains
exactly versioned and hash-locked in `requirements-build.lock`; it is not
duplicated as an application dependency lock.
