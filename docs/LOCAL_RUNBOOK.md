# Local runbook

## Scope

This runbook covers one local workflow store on a POSIX host.

## Baseline checks

```console
uv run --locked aidlc-v2 --store PATH status
uv run --locked aidlc-v2 --store PATH verify-audit
uv run --locked aidlc-v2 --store PATH outcomes
```

All reads validate state, policy binding, and the complete audit chain.

## Store layout

```text
PATH/
  state.json
  policy.json
  audit/
    00000001-event_....json
  .aidlc-v2.lock
```

The repository normalizes the project and audit directories to mode `0700`,
the lock/state/policy/pending files to owner access, and audit events to
owner-read-only.

## Pending transaction recovery

`.aidlc-v2.pending.json` means a mutation may have stopped after preparing its
event/state pair. Do not edit it.

1. Stop other engine processes using the store.
2. Run `verify-audit` or `status`.
3. The repository validates the pair and completes an idempotent append/state
   write when safe.
4. If validation fails, preserve the entire directory and investigate before
   attempting recovery.

Manual deletion of a pending marker can discard the only complete next-state
pair and is unsupported.

## Parked workflow

```console
uv run --locked aidlc-v2 --store PATH resume \
  --actor-id HUMAN_ID \
  --actor-kind human
```

Resume clears only the parked marker; it does not advance the cursor.
Autonomous Construction cannot be parked.

## Unit/Bolt failure

Inspect `workflow.failure` in `status`, then choose:

```console
uv run --locked aidlc-v2 --store PATH resolve-bolt-failure \
  --actor-id HUMAN_ID \
  --actor-kind human \
  --action retry
```

Valid actions are `retry`, `skip`, and `abort`. The walking-skeleton Unit
cannot be skipped. Ordinary workflow mutations remain blocked until the
decision. The command retains the upstream `Bolt` term for compatibility.

## Autonomy prompt

If `workflow.autonomy_prompt_pending` is true:

```console
uv run --locked aidlc-v2 --store PATH set-autonomy \
  --actor-id HUMAN_ID \
  --actor-kind human \
  --mode gated
```

The choice is one-time for the workflow iteration.

## Common errors

| Code | Meaning | Action |
| --- | --- | --- |
| `stage_outputs_missing` | Declared current outputs are absent | Register the listed artifacts |
| `stage_inputs_missing` | Active upstream producer evidence is absent | Complete or repair upstream evidence |
| `review_ready_required` | Reviewer loop has not reached READY/cap | Record the configured reviewer verdict |
| `self_approval_forbidden` | Gate requester attempted approval | Use a distinct human |
| `autonomy_choice_required` | Walking-skeleton ladder is pending | Set human autonomy mode |
| `bolt_failure_action_required` | A Unit failed | Retry, skip, or abort |
| `integrity_error` | State, policy, event order, or hash failed | Stop mutation and preserve the store |
| `unsafe_storage_path` | A key storage path is a symbolic link | Use a real local directory |

## Integrity incident

When verification fails:

1. stop all writers;
2. make a read-only copy of the entire store;
3. record filesystem metadata and the command/error JSON;
4. compare state revision, audit count, filenames, and final event digest;
5. do not rewrite event files to make verification pass; and
6. restore only from a separately validated backup.

The project has no automatic backup or trusted external checkpoint.

## Backup and restore

For evaluation only:

1. park or stop the workflow;
2. ensure no process holds the lock;
3. copy the entire directory, including hidden files and permissions;
4. verify the copied store independently; and
5. keep the original until the copy is confirmed.

This is not a certified production backup procedure.

## Clean evaluation data

Do not place credentials, customer records, private source, personal data, or
production artifacts in descriptions, rationales, summaries, or locators.
Artifact content remains outside the store; use only synthetic fixtures in
repository tests and examples.
