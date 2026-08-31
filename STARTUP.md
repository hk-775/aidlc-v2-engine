# Evaluator startup checklist

## Environment

- [ ] POSIX host
- [ ] Python 3.11+
- [ ] `uv` available
- [ ] no sensitive data in the evaluation workspace

```console
python3 --version
uv --version
uv sync --locked
uv run --locked aidlc-v2 --help
```

## Methodology baseline

- [ ] Read `docs/V2_REQUIREMENTS.md`.
- [ ] Confirm the official `v2` branch pin is framework version 2.6.124 at
  `82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d`.
- [ ] Understand that this is independent, not an official AWS release.

```console
uv run --locked aidlc-v2 catalog
```

Expected catalog totals: five phases, 33 stages, 11 core scopes, 11 domain
agents, and two reviewer agents.

## Repository validation

```console
make test
make scan
make demo
make package-check
make browser-check
```

Run `make coverage` and `make history-scan` before release review.

## Demo smoke test

```console
uv run --locked aidlc-v2 --store .tmp/startup-demo demo
uv run --locked aidlc-v2 --store .tmp/startup-demo verify-audit
uv run --locked aidlc-v2 --store .tmp/startup-demo outcomes
```

Confirm:

- workflow status is `completed`;
- scope is `bugfix`;
- visited stages are Reverse Engineering, Requirements Analysis, Code
  Generation, Build and Test, Deployment Pipeline, and Deployment Execution;
- the incremental route uses no synthetic Unit;
- 30 artifacts and six gates exist;
- 66 events verify successfully.

## Authority check

```console
uv run --locked aidlc-v2 --store .tmp/startup-demo guard-operation \
  --actor-id agent_builder \
  --actor-kind agent \
  --operation release
```

Confirm `forbidden_operation`.

## Operational cautions

- [ ] Identity and human status are asserted, not authenticated.
- [ ] Artifact bytes are external and not revalidated.
- [ ] Workspace-change evidence is caller asserted.
- [ ] Audit is tamper-evident, not signed or externally anchored.
- [ ] The store has no production backup or migration system.
- [ ] No merge, deploy, release, or cloud action is implemented.

## Documentation path

1. `README.md`
2. `QUICKSTART.md`
3. `docs/V2_REQUIREMENTS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/THREAT_MODEL.md`
6. `docs/PRODUCTION_READINESS.md`
7. `docs/CLEAN_ROOM_PROVENANCE.md`
