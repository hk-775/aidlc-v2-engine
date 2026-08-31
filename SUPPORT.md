# Support

AI-DLC v2 Engine is a community open-source alpha project with no paid support, uptime
commitment, response guarantee, or production service.

## Where to ask

- Use the
  [question form](https://github.com/hk-775/aidlc-v2-engine/issues/new?template=question.yml)
  for reproducible, non-sensitive usage questions.
- Use the
  [bug form](https://github.com/hk-775/aidlc-v2-engine/issues/new?template=bug.yml)
  for incorrect behavior.
- Use private vulnerability reporting as described in
  [SECURITY.md](SECURITY.md).
- Use governance processes for scope, conduct, or maintainer decisions.

Before asking, run:

```console
python3 --version
make test
make scan
make demo
```

Include the operating system, Python version, command, machine-readable error,
and a minimal synthetic reproduction. Do not attach a real project store if it
contains sensitive evidence or actor information.

## Scope

Community support can reasonably cover:

- local setup on a supported POSIX environment;
- policy validation;
- lifecycle, gate, reviewer, and Bolt behavior;
- audit verification;
- repository tests and scans; and
- documentation corrections.

It does not cover:

- production deployment design;
- legal, regulatory, certification, or compliance advice;
- incident response for third-party systems;
- custom delivery-system integrations; or
- recovery guarantees for corrupted or lost local data.
