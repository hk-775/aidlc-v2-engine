from __future__ import annotations

import contextlib
import io
import json
import tomllib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from aidlc_v2_engine.catalog import PHASES, SCOPES, STAGES, scope_summary
from tests.support import ROOT, WorkspaceTestCase
from tools.repo_scan import (
    REQUIRED_FILES,
    decoded_provenance_terms,
    main as repo_scan_main,
    run_scans,
    scan_credentials,
    scan_denylist,
    scan_external_assets,
    scan_formatting,
    scan_python_syntax,
    scan_workflows,
)


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.tags.append((tag, dict(attrs)))


class RepositoryHygieneTests(WorkspaceTestCase):
    def test_complete_repository_scan_passes(self) -> None:
        result = run_scans(ROOT)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["scan_count"], 9)

    def test_repository_scan_cli_defaults_to_all_scans(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return_code = repo_scan_main([])
        self.assertEqual(return_code, 0)
        self.assertEqual(json.loads(output.getvalue())["scan_count"], 9)

    def test_repository_scan_cli_rejects_unknown_selection(self) -> None:
        error = io.StringIO()
        with (
            contextlib.redirect_stderr(error),
            self.assertRaisesRegex(SystemExit, "2"),
        ):
            repo_scan_main(["not-a-scan"])
        self.assertIn("unknown scan selection", error.getvalue())

    def test_provenance_denylist_is_runtime_decoded_and_case_insensitive(self) -> None:
        root = self.workspace / "denylist"
        root.mkdir()
        term = decoded_provenance_terms()[0].upper()
        (root / "sample.txt").write_text(f"blocked: {term}\n", encoding="utf-8")
        findings = scan_denylist(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].scan, "denylist")

    def test_credential_scan_detects_synthetic_access_key_shape(self) -> None:
        root = self.workspace / "credentials"
        root.mkdir()
        fake_value = "AK" + "IA" + ("A" * 16)
        (root / "sample.txt").write_text(fake_value + "\n", encoding="utf-8")
        findings = scan_credentials(root)
        self.assertEqual(len(findings), 1)

    def test_external_asset_scan_detects_network_script(self) -> None:
        root = self.workspace / "external"
        site = root / "site"
        site.mkdir(parents=True)
        remote = "https:" + "//example.invalid/app.js"
        (site / "index.html").write_text(
            f'<script src="{remote}"></script>\n',
            encoding="utf-8",
        )
        self.assertEqual(len(scan_external_assets(root)), 1)

    def test_external_asset_scan_allows_navigation_links(self) -> None:
        root = self.workspace / "external-navigation"
        site = root / "site"
        site.mkdir(parents=True)
        remote = "https:" + "//example.invalid/project"
        (site / "index.html").write_text(
            f'<a href="{remote}">Repository</a>\n',
            encoding="utf-8",
        )
        self.assertEqual(scan_external_assets(root), [])

    def test_workflow_scan_detects_unpinned_action(self) -> None:
        root = self.workspace / "workflow"
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "bad.yml").write_text(
            "\n".join(
                (
                    "name: Bad workflow",
                    "on: workflow_dispatch",
                    "permissions:",
                    "  contents: read",
                    "jobs:",
                    "  test:",
                    "    runs-on: ubuntu-24.04",
                    "    steps:",
                    "      - uses: actions/checkout@v4",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                )
            ),
            encoding="utf-8",
        )
        findings = scan_workflows(root)
        self.assertTrue(
            any("not pinned to a full commit" in finding.message for finding in findings)
        )

    def test_formatting_scan_detects_whitespace_and_eof_errors(self) -> None:
        root = self.workspace / "formatting"
        root.mkdir()
        (root / "sample.md").write_text("bad line \n\n", encoding="utf-8")
        messages = {finding.message for finding in scan_formatting(root)}
        self.assertEqual(
            messages,
            {"trailing whitespace", "extra blank line at end of file"},
        )

    def test_formatting_scan_skips_binary_assets(self) -> None:
        root = self.workspace / "binary-formatting"
        root.mkdir()
        (root / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff")
        self.assertEqual(scan_formatting(root), [])

    def test_python_syntax_scan_detects_invalid_source(self) -> None:
        root = self.workspace / "syntax"
        root.mkdir()
        (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        self.assertEqual(len(scan_python_syntax(root)), 1)

    def test_required_open_source_and_v2_baseline_artifacts_exist(self) -> None:
        missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])
        for path in (
            "docs/V2_REQUIREMENTS.md",
            "docs/CLEAN_ROOM_PROVENANCE.md",
            "src/aidlc_v2_engine/data/stage-catalog.json",
            "src/aidlc_v2_engine/data/scope-grid.json",
        ):
            self.assertIn(path, REQUIRED_FILES)

    def test_no_permanent_package_archives_exist(self) -> None:
        archives = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and ".tmp" not in path.parts
            and (
                path.suffix in {".whl", ".zip"}
                or path.name.endswith(".tar.gz")
            )
        ]
        self.assertEqual(archives, [])

    def test_lock_manifest_and_package_identity_are_exact(self) -> None:
        runtime_lines = [
            line
            for line in (ROOT / "requirements.lock").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(runtime_lines, [])

        build_lock = (ROOT / "requirements-build.lock").read_text(encoding="utf-8")
        self.assertGreaterEqual(build_lock.count("--hash=sha256:"), 12)
        uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        self.assertEqual(uv_lock["version"], 1)
        self.assertEqual(uv_lock["requires-python"], ">=3.11")
        locked_names = {package["name"] for package in uv_lock["package"]}
        self.assertTrue(
            {
                "aidlc-v2-engine",
                "build",
                "coverage",
                "setuptools",
                "wheel",
            }.issubset(locked_names)
        )
        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(pyproject["build-system"]["requires"], ["setuptools==84.0.0"])
        self.assertEqual(
            pyproject["project"]["scripts"],
            {"aidlc-v2": "aidlc_v2_engine.cli:main"},
        )
        self.assertEqual(
            pyproject["tool"]["setuptools"]["package-data"]["aidlc_v2_engine"],
            ["data/*.json"],
        )
        self.assertEqual(
            pyproject["dependency-groups"]["dev"],
            [
                "build==1.3.0",
                "coverage==7.13.4",
                "setuptools==84.0.0",
                "wheel==0.48.0",
            ],
        )

    def test_uv_is_the_primary_installation_path(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for text in (readme, quickstart, contributing):
            self.assertIn("uv sync --locked", text)
            self.assertIn("uv run --locked", text)
        self.assertNotIn("uv pip install", contributing)

    def test_publication_inventory_covers_v2_customer_artifacts(self) -> None:
        inventory = (ROOT / "docs" / "PUBLICATION_ARTIFACTS.md").read_text(
            encoding="utf-8"
        )
        for path in (
            "site/index.html",
            "site/architecture.html",
            "site/assets/architecture.drawio",
            "site/assets/architecture.png",
            "docs/V2_REQUIREMENTS.md",
            "docs/CLEAN_ROOM_PROVENANCE.md",
            "docs/ARCHITECTURE.md",
            "docs/PRODUCTION_READINESS.md",
            "launch-materials.md",
        ):
            with self.subTest(path=path):
                self.assertIn(path, inventory)

    def test_pages_deployment_is_manual_main_only_and_permission_scoped(self) -> None:
        text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        trigger_block, jobs_block = text.split("jobs:", 1)
        self.assertNotIn("\n  push:", trigger_block)
        self.assertNotIn("pages: write", trigger_block)
        self.assertNotIn("id-token: write", trigger_block)
        self.assertIn("github.ref == 'refs/heads/main'", jobs_block)
        self.assertIn("ref: refs/heads/main", jobs_block)
        self.assertIn("pages: write", jobs_block)
        self.assertIn("id-token: write", jobs_block)
        self.assertIn("uv sync --locked", jobs_block)
        self.assertIn("tools/browser_check.py", jobs_block)

    def test_browser_check_covers_pages_base_interactions_and_network(self) -> None:
        script = (ROOT / "tools" / "browser_check.py").read_text(encoding="utf-8")
        for marker in (
            'DEFAULT_BASE_PATH = "/aidlc-v2-engine/"',
            '"Network.requestWillBeSent"',
            '"Network.webSocketCreated"',
            "assert_mobile_layout",
            'session.click("#next-step")',
            'session.click(\'[data-scenario="governance"]\')',
            "--base-url",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)


class StaticSiteTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.page_text: dict[str, str] = {}
        self.page_parsers: dict[str, SiteParser] = {}
        for name in ("index.html", "architecture.html"):
            text = (ROOT / "site" / name).read_text(encoding="utf-8")
            parser = SiteParser()
            parser.feed(text)
            self.page_text[name] = text
            self.page_parsers[name] = parser
        self.index_text = self.page_text["index.html"]
        self.architecture_text = self.page_text["architecture.html"]
        self.index_parser = self.page_parsers["index.html"]

    def test_page_has_language_landmarks_and_v2_heading(self) -> None:
        html_attrs = next(
            attrs for tag, attrs in self.index_parser.tags if tag == "html"
        )
        tags = [tag for tag, _ in self.index_parser.tags]
        self.assertEqual(html_attrs.get("lang"), "en")
        for landmark in ("header", "nav", "main", "footer", "h1"):
            self.assertIn(landmark, tags)
        self.assertIn("Automate AI-DLC v2. Keep authority human.", self.index_text)
        self.assertIn("Independent AI-DLC v2 automation", self.index_text)

    def test_site_claims_match_the_pinned_catalog(self) -> None:
        self.assertEqual(len(PHASES), 5)
        self.assertEqual(len(STAGES), 33)
        self.assertEqual(len(SCOPES), 11)
        self.assertIn("five-phase, 33-stage", self.index_text)
        self.assertIn("11 exact core scope grids", self.index_text)
        self.assertIn("framework version 2.6.124", self.index_text)
        self.assertNotIn("Six adjacent stages", self.index_text)

        expected_counts = {
            "enterprise": 33,
            "feature": 33,
            "mvp": 23,
            "poc": 8,
            "bugfix": 9,
            "refactor": 10,
            "infra": 13,
            "security-patch": 10,
            "classic": 26,
            "workshop": 26,
            "express": 10,
        }
        self.assertEqual(
            {
                scope: scope_summary(scope)["active_stage_count"]
                for scope in SCOPES
            },
            expected_counts,
        )

    def test_skip_link_targets_main_content(self) -> None:
        anchors = [attrs for tag, attrs in self.index_parser.tags if tag == "a"]
        self.assertTrue(any(attrs.get("href") == "#main" for attrs in anchors))
        main = next(
            attrs for tag, attrs in self.index_parser.tags if tag == "main"
        )
        self.assertEqual(main.get("id"), "main")

    def test_every_image_has_nonempty_alt_text(self) -> None:
        for page_name, parser in self.page_parsers.items():
            with self.subTest(page=page_name):
                images = [attrs for tag, attrs in parser.tags if tag == "img"]
                self.assertGreaterEqual(len(images), 1)
                self.assertTrue(all(attrs.get("alt") for attrs in images))

    def test_content_policy_disables_network_connections(self) -> None:
        for page_name, parser in self.page_parsers.items():
            with self.subTest(page=page_name):
                metas = [attrs for tag, attrs in parser.tags if tag == "meta"]
                policy = next(
                    attrs["content"]
                    for attrs in metas
                    if attrs.get("http-equiv") == "Content-Security-Policy"
                )
                self.assertIn("connect-src 'none'", policy)
                self.assertIn("object-src 'none'", policy)

    def test_all_referenced_site_assets_exist(self) -> None:
        loaded_relations = {
            "icon",
            "manifest",
            "modulepreload",
            "preload",
            "stylesheet",
        }
        for page_name, parser in self.page_parsers.items():
            referenced: list[str] = []
            for tag, attrs in parser.tags:
                if tag in {"img", "script"} and attrs.get("src"):
                    referenced.append(str(attrs["src"]))
                relations = set((attrs.get("rel") or "").split())
                if (
                    tag == "link"
                    and relations & loaded_relations
                    and attrs.get("href")
                ):
                    referenced.append(str(attrs["href"]))
            for reference in referenced:
                with self.subTest(page=page_name, reference=reference):
                    self.assertTrue((ROOT / "site" / reference).is_file())

    def test_canonical_and_repository_links_are_configured(self) -> None:
        expected = {
            "index.html": "https://hk-775.github.io/aidlc-v2-engine/",
            "architecture.html": (
                "https://hk-775.github.io/aidlc-v2-engine/architecture.html"
            ),
        }
        for page_name, canonical_url in expected.items():
            links = [
                attrs
                for tag, attrs in self.page_parsers[page_name].tags
                if tag == "link"
            ]
            canonical = next(
                attrs
                for attrs in links
                if "canonical" in (attrs.get("rel") or "").split()
            )
            self.assertEqual(canonical.get("href"), canonical_url)
        anchors = [
            attrs for tag, attrs in self.index_parser.tags if tag == "a"
        ]
        self.assertTrue(
            any(
                attrs.get("href") == "https://github.com/hk-775/aidlc-v2-engine"
                for attrs in anchors
            )
        )

    def test_javascript_uses_safe_local_rendering(self) -> None:
        for name in ("app.js", "architecture.js"):
            with self.subTest(name=name):
                script = (ROOT / "site" / name).read_text(encoding="utf-8")
                self.assertNotIn("innerHTML", script)
                self.assertIn("textContent", script)
                self.assertNotIn("fetch(", script)

    def test_architecture_explorer_covers_v2_flows_and_downloads(self) -> None:
        self.assertIn("Interactive architecture", self.architecture_text)
        self.assertIn('id="architecture-steps"', self.architecture_text)
        for path in (
            "assets/architecture.drawio",
            "assets/architecture.png",
            "assets/architecture.svg",
            "assets/architecture.dot",
        ):
            self.assertIn(path, self.architecture_text)
        script = (ROOT / "site" / "architecture.js").read_text(encoding="utf-8")
        for marker in (
            "lifecycle: Object.freeze({",
            "governance: Object.freeze({",
            "construction: Object.freeze({",
            "persistence: Object.freeze({",
            "walking-skeleton",
            "window.setInterval",
        ):
            self.assertIn(marker, script)

    def test_svg_assets_are_well_formed_and_described(self) -> None:
        for name in (
            "aidlc-v2-engine-logo.svg",
            "aidlc-v2-engine-icon.svg",
            "architecture.svg",
        ):
            with self.subTest(name=name):
                root = ET.parse(ROOT / "site" / "assets" / name).getroot()
                local_names = {
                    child.tag.rsplit("}", 1)[-1] for child in list(root)
                }
                self.assertIn("title", local_names)
                self.assertIn("desc", local_names)

    def test_architecture_sources_and_render_are_v2_aligned(self) -> None:
        dot_source = (ROOT / "site" / "assets" / "architecture.dot").read_text(
            encoding="utf-8"
        )
        drawio_root = ET.parse(
            ROOT / "site" / "assets" / "architecture.drawio"
        ).getroot()
        drawio_values = " ".join(
            element.attrib.get("value", "") for element in drawio_root.iter()
        )
        svg = (ROOT / "site" / "assets" / "architecture.svg").read_text(
            encoding="utf-8"
        )
        png = (ROOT / "site" / "assets" / "architecture.png").read_bytes()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(drawio_root.tag, "mxfile")
        for marker in (
            "Pinned v2 catalog",
            "Stage-major Unit controls",
            "Worker / model harness",
        ):
            self.assertIn(marker, dot_source)
            self.assertIn(marker, drawio_values)
            self.assertIn(marker.split(" controls")[0], svg)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png[12:16], b"IHDR")
        self.assertEqual(int.from_bytes(png[16:20], "big"), 1600)
        self.assertEqual(int.from_bytes(png[20:24], "big"), 900)
        self.assertIn("site/assets/architecture.png", readme)
        self.assertIn("site/assets/architecture.drawio", readme)

    def test_static_demo_matches_the_executable_bugfix_demo(self) -> None:
        script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        for marker in (
            'scope: "bugfix"',
            'status: "completed"',
            '"reverse-engineering"',
            '"requirements-analysis"',
            '"code-generation"',
            '"build-and-test"',
            '"deployment-pipeline"',
            '"deployment-execution"',
            "artifacts: 30",
            "gates: 6",
            "units: 0",
            "auditEvents: 66",
        ):
            self.assertIn(marker, script)
        self.assertNotIn('currentStage: "release"', script)
