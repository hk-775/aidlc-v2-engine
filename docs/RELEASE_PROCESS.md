# Release process

AI-DLC v2 Engine releases are source-reviewed alpha artifacts. A release is not a
production-readiness claim, and the automated workflow does not publish to
PyPI or another package index.

## Preconditions

1. Complete [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
2. Confirm `pyproject.toml` and `src/aidlc_v2_engine/__init__.py` contain the same strict
   semantic version.
3. Confirm `CHANGELOG.md` describes the release and its limitations.
4. Obtain the governance and independent security reviews required by
   [GOVERNANCE.md](../GOVERNANCE.md).
5. Run `make check`, `make coverage`, and `make history-scan` from a clean
   checkout.
6. Confirm CI and release workflows install `requirements-build.lock` with
   pip hash enforcement.

## Create the tag

Release tags use the exact form `vMAJOR.MINOR.PATCH` and must be annotated.

```console
git tag -s v0.1.0 -m "AI-DLC v2 Engine 0.1.0"
git push origin v0.1.0
```

If signed tags are not yet available, use an annotated tag and record that
limitation:

```console
git tag -a v0.1.0 -m "AI-DLC v2 Engine 0.1.0"
git push origin v0.1.0
```

Do not move or replace a published release tag. Correct a bad release with a
new version.

## Automated verification

The `Build release artifacts` workflow checks out the exact tag with complete
history, then:

1. verifies that the annotated tag, package version, and checked-out commit
   agree;
2. installs the exact hash-locked build and coverage toolchain;
3. runs tests, repository scans, coverage, the synthetic demo, package
   inspection, and reachable-history scanning;
4. builds one source archive and one universal wheel;
5. verifies the exact archive names and records SHA-256 digests; and
6. uploads the archives as a retained GitHub Actions artifact.

The workflow has read-only repository permission. It does not create a GitHub
Release, publish a package, sign an archive, or deploy software.

## Publish deliberately

After the workflow succeeds, a release steward downloads the workflow
artifact, independently verifies the recorded digests, and prepares release
notes that link to:

- the changelog;
- current limitations and production-readiness ledger;
- security reporting instructions; and
- any bootstrap-governance or unsigned-artifact disclosure.

Creating a GitHub Release or publishing to a package index is a separate human
decision. No automation in this repository performs that action.
