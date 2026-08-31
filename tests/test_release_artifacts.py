from __future__ import annotations

import io
import tarfile
import zipfile

from tests.support import ROOT, WorkspaceTestCase
from tools.release_check import (
    ReleaseCheckError,
    read_version,
    validate_release_tag,
    verify_distribution,
)


class ReleaseArtifactTests(WorkspaceTestCase):
    def test_source_and_package_versions_match(self) -> None:
        self.assertEqual(read_version(ROOT), "0.1.0")

    def test_release_tag_must_exactly_match_version(self) -> None:
        validate_release_tag("v0.1.0", "0.1.0")
        with self.assertRaisesRegex(ReleaseCheckError, "must be v0.1.0"):
            validate_release_tag("0.1.0", "0.1.0")

    def test_distribution_names_and_digests_are_verified(self) -> None:
        distribution = self.workspace / "dist"
        distribution.mkdir()
        names = (
            "aidlc_v2_engine-0.1.0-py3-none-any.whl",
            "aidlc_v2_engine-0.1.0.tar.gz",
        )
        wheel = distribution / names[0]
        with zipfile.ZipFile(wheel, "w") as archive:
            for member in (
                "aidlc_v2_engine/__init__.py",
                "aidlc_v2_engine/catalog.py",
                "aidlc_v2_engine/cli.py",
                "aidlc_v2_engine/data/scope-grid.json",
                "aidlc_v2_engine/data/stage-catalog.json",
                "aidlc_v2_engine/service.py",
                "aidlc_v2_engine-0.1.0.dist-info/licenses/LICENSE",
                "aidlc_v2_engine-0.1.0.dist-info/licenses/NOTICE",
            ):
                archive.writestr(member, "synthetic\n")
            archive.writestr(
                "aidlc_v2_engine-0.1.0.dist-info/METADATA",
                "\n".join(
                    (
                        "License-Expression: Apache-2.0",
                        "License-File: LICENSE",
                        "License-File: NOTICE",
                        "Project-URL: Repository, https://github.com/hk-775/aidlc-v2-engine",
                        "Project-URL: Security, https://github.com/hk-775/aidlc-v2-engine/security/policy",
                        "",
                    )
                ),
            )
            archive.writestr(
                "aidlc_v2_engine-0.1.0.dist-info/entry_points.txt",
                "[console_scripts]\n"
                "aidlc-v2 = aidlc_v2_engine.cli:main\n",
            )
        source = distribution / names[1]
        with tarfile.open(source, "w:gz") as archive:
            for member in (
                ".github/workflows/release.yml",
                ".gitleaksignore",
                "CODEOWNERS",
                "README.md",
                "docs/PUBLICATION_ARTIFACTS.md",
                "docs/RELEASE_PROCESS.md",
                "docs/V2_REQUIREMENTS.md",
                "examples/evidence/README.md",
                "examples/evidence/build-and-test-summary.md",
                "examples/evidence/business-overview.md",
                "examples/evidence/code-summary.md",
                "examples/evidence/requirements.md",
                "examples/policy.strict.json",
                "requirements-build.lock",
                "schemas/policy.schema.json",
                "site/assets/architecture.drawio",
                "site/assets/architecture.png",
                "site/architecture.html",
                "site/architecture.js",
                "site/index.html",
                "tests/test_lifecycle.py",
                "tools/browser_check.py",
                "tools/history_scan.py",
                "tools/release_check.py",
                "uv.lock",
            ):
                content = b"synthetic\n"
                info = tarfile.TarInfo(f"aidlc_v2_engine-0.1.0/{member}")
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))

        artifacts = verify_distribution(distribution, "0.1.0")
        self.assertEqual([artifact["name"] for artifact in artifacts], list(names))
        self.assertTrue(all(len(str(artifact["sha256"])) == 64 for artifact in artifacts))

    def test_unexpected_distribution_file_is_rejected(self) -> None:
        distribution = self.workspace / "bad-dist"
        distribution.mkdir()
        (distribution / "unexpected.zip").write_bytes(b"synthetic")
        with self.assertRaisesRegex(ReleaseCheckError, "distribution mismatch"):
            verify_distribution(distribution, "0.1.0")
