# AI-DLC v2 Engine quickstart

## Install

AI-DLC v2 Engine requires Python 3.11+ and a POSIX host.

```console
uv tool install .
aidlc-v2 --help
```

## Run the complete synthetic demo

```console
aidlc-v2 --store .tmp/quickstart-demo demo
```

Expected summary:

- `"scope": "bugfix"`
- `"status": "completed"`
- `"artifact_count": 30`
- `"gate_count": 6`
- `"unit_count": 0`
- `"event_count": 66`
- `"audit_valid": true`

Inspect the result:

```console
aidlc-v2 --store .tmp/quickstart-demo status
aidlc-v2 --store .tmp/quickstart-demo outcomes
aidlc-v2 --store .tmp/quickstart-demo verify-audit
aidlc-v2 --store .tmp/quickstart-demo events
```

## Inspect and route the methodology

```console
aidlc-v2 catalog

aidlc-v2 detect-scope \
  --description "Patch a CVE vulnerability in the parser"
```

Ambiguous matches and rich freeform descriptions fail with
`scope_composition_required`. Choose a scope explicitly or compose the plan
with a human decision. Short descriptions without a specialized keyword use
the current `classic` default.

## Initialize a manual workflow

```console
aidlc-v2 \
  --store .tmp/manual \
  --id-seed manual-example \
  --fixed-time 2026-08-30T09:00:00Z \
  init \
  --name "Parser repair" \
  --description "Fix a deterministic parser bug" \
  --workspace-kind brownfield \
  --scope bugfix \
  --actor-id human_owner \
  --actor-kind human \
  --role workflow_owner
```

The three Initialization stages complete automatically. The `bugfix` scope
then starts at `reverse-engineering`.

## Complete one stage

Query `status` and read the current stage’s declared outputs from `catalog`.
For `reverse-engineering`, register each declared output:

```console
aidlc-v2 \
  --store .tmp/manual \
  add-artifact \
  --actor-id aidlc-developer-agent \
  --actor-kind agent \
  --name business-overview \
  --title "Business overview" \
  --digest sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --locator evidence/reverse-engineering/business-overview.md
```

Repeat for the remaining declared outputs, then open the gate:

```console
aidlc-v2 \
  --store .tmp/manual \
  request-approval \
  --actor-id aidlc-developer-agent \
  --actor-kind agent \
  --rationale "Declared outputs are complete"
```

Copy the returned gate identifier and approve it with a different human:

```console
aidlc-v2 \
  --store .tmp/manual \
  approve-stage \
  --actor-id human_owner \
  --actor-kind human \
  --role workflow_owner \
  --gate-id gate_REPLACE_ME
```

Stages that declare a reviewer require a READY verdict or exhaustion of the
bounded reviewer loop before the human gate can open:

```console
aidlc-v2 \
  --store .tmp/manual \
  record-review \
  --actor-id aidlc-product-lead-agent \
  --actor-kind agent \
  --verdict ready \
  --summary "Requirements are ready for human judgment"
```

## Construction controls

Create Units before Construction when the selected scope includes
`units-generation`:

```console
aidlc-v2 \
  --store .tmp/manual \
  add-unit \
  --actor-id aidlc-developer-agent \
  --actor-kind agent \
  --name "Walking skeleton" \
  --kind service
```

Construction walks stage-major by default: finish the active stage for each
Unit, then open one stage-level gate. After registering the current Unit’s
outputs and reviewer evidence, settle that Unit:

```console
aidlc-v2 \
  --store .tmp/manual \
  complete-unit-stage \
  --actor-id aidlc-developer-agent \
  --actor-kind agent
```

Repeat for every Unit, then use `request-approval`. After the first
Construction stage gate, a human selects the one-time ladder mode:

```console
aidlc-v2 \
  --store .tmp/manual \
  set-autonomy \
  --actor-id human_owner \
  --actor-kind human \
  --mode gated
```

Scopes that skip `units-generation` use a zero-Unit stage-level path; the
engine does not invent a synthetic Unit. Any Unit failure halts progress until
a human chooses `retry`, `skip`, or `abort`.

## Observe a hard denial

```console
aidlc-v2 \
  --store .tmp/quickstart-demo \
  guard-operation \
  --actor-id agent_builder \
  --actor-kind agent \
  --operation release
```

The command returns `forbidden_operation`. Policy cannot enable external
release authority for an agent.

## Run repository checks

```console
make test
make coverage
make scan
make history-scan
make demo
make package-check
```
