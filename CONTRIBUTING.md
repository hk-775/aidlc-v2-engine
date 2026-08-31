# Contributing to AI-DLC v2 Engine

Thank you for helping improve a human-governed approach to agent-assisted
delivery.

## Before starting

Open an issue for changes that alter the lifecycle, policy invariants, storage
format, public CLI, security boundary, governance model, or licensing. Small
documentation and test corrections can proceed directly.

Do not submit:

- proprietary, confidential, personal, or customer-derived material;
- copied code, wording, tests, diagrams, policies, or examples without a clear
  compatible license and attribution;
- real credentials, production endpoints, or sensitive evidence;
- changes that let an agent approve, merge, deploy, release, accept risk,
  satisfy a human gate, or bypass policy; or
- generated package archives and local project stores.

## Development setup

Python 3.11 or newer is required. Runtime dependencies are intentionally empty.
Create the reviewed development environment directly from the committed lock:

```console
uv sync --locked
uv run --locked aidlc-v2 --help
```

```console
make test
make coverage
make scan
make history-scan
make demo
make package-check
make browser-check
```

Chrome or Chromium is required for `make browser-check`. Make targets invoke
Python with `uv run --locked` and set `PYTHONPATH=src`.

## Design expectations

- Preserve deterministic behavior when timestamp and identifier providers are
  injected.
- Keep state changes inside repository transactions.
- Use explicit error subclasses and stable error codes.
- Reject unknown or unsafe policy fields.
- Add an audit event for every state mutation.
- Keep examples synthetic and industry-neutral.
- Document limitations alongside new capabilities.
- Prefer the standard library unless a dependency has a clear, reviewed need.

## Tests

Add tests for success, denial, malformed input, persistence, and audit effects.
Tests must not use network access or write outside their temporary directory.
When changing stored data, update the relevant JSON Schema and compatibility
notes.

## Documentation

Use original wording. Claims must describe behavior that the repository can
demonstrate now. Avoid certification, compliance, scale, security, and
production-readiness claims without evidence.

## Pull requests

A pull request should:

1. explain the user-visible problem;
2. describe the chosen boundary and alternatives;
3. identify security or governance effects;
4. list validation performed;
5. update documentation and changelog entries when appropriate; and
6. confirm provenance and synthetic-data requirements.

Workflow changes must pin external actions to full commit identifiers and
disable persisted checkout credentials. Release changes must follow
[docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

At least one maintainer reviews ordinary changes. Changes to hard safety
invariants, schemas, security boundaries, governance, or releases require two
maintainer approvals, including one designated security reviewer.

## Certificate of origin

By contributing, you certify that you have the right to submit the work under
the project license and that the contribution does not knowingly include
material from an incompatible or undisclosed source.
