# Responsible use

## Intended use

Use AI-DLC v2 Engine for local evaluation, education, control-plane
experimentation, and non-production workflow design with synthetic or
low-sensitivity material.

Suitable work includes:

- comparing scope plans;
- testing artifact and gate rules;
- exercising reviewer and revision flows;
- studying walking-skeleton autonomy and failures;
- testing navigation and learning controls; and
- verifying local audit behavior.

## Human responsibility

An engine gate is a record, not proof of competent review. Human decision-makers
must inspect evidence, verify external content against its digest, understand
impact, disclose conflicts, reject uncertainty, and resist automation pressure.

The engine does not prove that a caller is human, that two identifiers are
different people, or that a decision is legally or professionally sufficient.

## Agent boundary

Do not embed the engine in a way that:

- labels an agent as human;
- gives an agent human credentials;
- automatically approves its own gate;
- treats reviewer output as final authority;
- converts a workflow stage into merge/deploy/release permission;
- ignores the Unit/Bolt failure envelope; or
- treats generated artifacts as verified facts.

## Data handling

The local store is not encrypted. Avoid:

- credentials and private keys;
- personal, medical, financial, employment, or regulated records;
- confidential source, designs, incidents, or customer material;
- production endpoints and identifiers; and
- proprietary evidence without authorization.

Artifact bytes are not stored, but titles, descriptions, rationales, summaries,
digests, and locators are.

## High-impact decisions

Do not rely on this alpha for safety-critical, medical, financial, legal,
employment, public-infrastructure, or similarly high-impact decisions. The
project claims no compliance or certification.

## Misleading claims to avoid

Do not present:

- a completed workflow as proof that software shipped safely;
- autonomous mode as unsupervised production authority;
- a valid hash chain as actor authentication or non-repudiation;
- a READY review as independent assurance;
- passing repository checks as a security certification; or
- methodology conformance as legal compliance.

## Over-reliance signals

Investigate:

- approvals immediately following machine requests;
- one person using multiple identities;
- identical evidence across unrelated stages;
- repeated accept-as-is decisions;
- unjustified jumps or recompositions;
- ignored sensor failures;
- repeated Unit/Bolt failure skips;
- unexplained integrity failures; and
- external automation triggered solely by state.

Report authority bypass, data exposure, or audit-integrity issues through the
private process in [`SECURITY.md`](../SECURITY.md).
