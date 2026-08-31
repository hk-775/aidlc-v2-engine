# AI-DLC v2 Engine governance

This document describes the intended governance model for an independent
open-source project. The GitHub account `@hk-775` is the bootstrap repository
steward, maintainer, security contact, and release steward until additional
maintainers are appointed. These roles describe project responsibility; they
do not imply independent assurance, certification, or warranty.

## Principles

- Human authority remains explicit and reviewable.
- Security and provenance concerns can block a release.
- Decisions and dissent are recorded in public project artifacts when privacy
  permits.
- Maintainer power is limited by review and conflict-of-interest rules.
- Maturity claims follow demonstrated evidence.

## Roles

### Contributors

Anyone who submits an issue, review, documentation, code, test, design, or
other accepted project material.

### Maintainers

Contributors trusted to triage, review, merge, and steward one or more project
areas. Maintainers are expected to model the code of conduct, preserve safety
invariants, and participate regularly.

### Security reviewers

Maintainers designated to review threat boundaries, disclosures, cryptographic
claims, dependency changes, and release risk. This designation does not imply a
certification or warranty.

### Release stewards

Maintainers who coordinate a release checklist, versioning, provenance review,
and artifact verification. Release stewards cannot waive required approvals.

## Bootstrap period

The project begins with one repository steward. During this period:

- ordinary changes require the steward's review or a recorded independent
  review when the steward authored the change;
- lifecycle, security, schema, governance, dependency, and public-release
  changes require an independent security review recorded in an issue or pull
  request;
- the steward cannot represent that a self-review is independent; and
- any release without the normally required two maintainers must disclose the
  bootstrap exception in its release notes.

The standard two-maintainer rules below take effect as soon as a second
maintainer and a designated security reviewer are appointed.

## Decision process

Routine changes use lazy consensus after at least one approving maintainer
review. The following require two approving maintainers, including a security
reviewer:

- lifecycle or authority-boundary changes;
- stored schema changes;
- weakening a default control;
- new external integration or runtime dependency;
- governance, license, or conduct changes; and
- a public release.

When consensus cannot be reached, maintainers document the options and call a
simple majority vote. A tied vote leaves the current behavior unchanged.
Security reviewers can place a temporary release hold for a specific,
documented risk. The hold must be reviewed by the maintainer group rather than
remaining indefinite without explanation.

## Appointing maintainers

An existing maintainer can nominate a contributor with a sustained record of
constructive, provenance-safe work. Appointment requires two-thirds approval
from active maintainers and no unresolved conduct or security concern.

## Inactivity and removal

A maintainer can move to emeritus status after six months without project
activity. Access can be suspended immediately for a credible security or
conduct risk, followed by documented review. Permanent removal requires a
two-thirds vote excluding conflicted members.

## Conflicts of interest

Reviewers disclose employment, financial, personal, or competitive interests
that could reasonably affect a decision. A conflicted maintainer may provide
technical context but does not cast the deciding vote.

## Appeals

A contributor can request reconsideration by identifying the decision, new
evidence, and desired remedy. A maintainer who did not make the original
decision leads the review.

## Amendments

Governance amendments require a public proposal, at least 14 days for comment,
and two-thirds approval from active maintainers.
