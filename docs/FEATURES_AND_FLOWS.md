# Features and flows

## Workflow initialization

1. A human supplies intent, workspace kind, and either an explicit or automatic
   scope.
2. Scope selects an exact execute/skip grid plus depth and test defaults.
3. Workspace Scaffold, Workspace Detection, and State Initialization complete
   automatically.
4. The first active non-initialization stage becomes current.
5. `WORKFLOW_STARTED` binds the initial state and policy digest.

Ambiguous automatic routing fails before storage initialization.

## Stage work

For the current stage context:

1. callers can record Guide, Edit File, or Chat answers;
2. agents or humans register only artifacts declared by that stage;
3. advisory sensor outcomes may be recorded;
4. configured reviewer agents record READY or NOT-READY;
5. the requester opens a gate after all deterministic guards pass; and
6. a distinct human approves or rejects.

Rejection moves the context to revising and increments its revision count.
After the configured limit, the human may accept as-is without bypassing
artifact or input guards.

## Artifact flow

Every artifact record includes:

- canonical lowercase kebab-case name;
- producing stage and optional Unit;
- title;
- SHA-256 digest;
- safe relative locator;
- workspace-change assertion;
- submitter; and
- timestamp.

The engine stores metadata, not artifact content. Duplicate stage/Unit/name
versions with the same digest are rejected. A changed digest records an
artifact update event.

## Reviewer flow

Stages with reviewer metadata use an independent loop:

1. reviewer reads the current stage context;
2. reviewer records READY or NOT-READY;
3. the builder may revise and request another review;
4. the loop stops at READY or the iteration cap; and
5. the human retains final gate authority.

An agent can record a verdict only when its asserted identifier matches the
configured reviewer agent.

## Scope and composition flow

Scope presets create the initial plan. A human can later recompose only
pending, ahead-of-cursor stages.

The engine freezes:

- Initialization;
- completed or in-progress work;
- behind-cursor work;
- the first executable Construction stage; and
- all recomposition while Construction autonomy is active.

The change and reason are audited as `RECOMPOSED`.

## Unit and Bolt flow

Units carry kind, order, dependencies, walking-skeleton marker, aggregate
status, and per-Unit Construction stage states.

```text
first in-scope Construction stage
  Unit 1 (walking skeleton) -> Unit 2 -> ... -> Unit N
                                      |
                              one aggregate gate
                                      |
                               autonomy ladder
                                      |
                   +------------------+------------------+
                   |                                     |
                 gated                               autonomous
                   |                                     |
     one gate after each later stage        later stages complete after
                   |                        deterministic evidence checks
                   +------------------+------------------+
                                      |
                       next stage across every Unit
                                      |
                           build-and-test once
                                      |
                              ci-pipeline once
```

Scopes without a Unit DAG execute their declared per-Unit stages once at stage
level and do not receive a synthetic Unit. Failure always exits the ordinary
path. A human must retry, skip an eligible non-skeleton Unit, or abort. The
walking-skeleton Unit cannot be skipped.

## Navigation flow

Human-only navigation supports:

- early-phase skip;
- audited forward jump;
- redo current context;
- independent depth/test changes;
- park and resume; and
- a new iteration after completion.

Park is refused during autonomous Construction because no human is guaranteed
to resume an unattended run.

## Learning flow

Agents or humans can propose memory-diary candidates:

- interpretation;
- deviation;
- tradeoff; or
- open question.

A human may keep a non-question candidate at project or team scope or reject
it. Kept learning is marked effective for the next workflow. No automatic
organization promotion occurs.

## Audit and recovery flow

Every mutation:

1. locks the project;
2. recovers a valid pending pair;
3. validates policy and state;
4. verifies the entire audit chain;
5. applies and validates the next state;
6. writes a pending event/state pair;
7. appends the event exclusively;
8. atomically replaces state;
9. verifies the resulting chain; and
10. removes the pending marker.

Read-only commands also verify the chain before returning data.

## Stable error families

Common errors include:

- `scope_composition_required`
- `stage_outputs_missing`
- `stage_inputs_missing`
- `workspace_change_required`
- `review_ready_required`
- `self_approval_forbidden`
- `revision_limit_not_reached`
- `walking_skeleton_anchor_frozen`
- `autonomy_choice_required`
- `bolt_failure_action_required`
- `walking_skeleton_required`
- `forbidden_operation`
- `integrity_error`

Expected errors are emitted as JSON and do not mutate state.
