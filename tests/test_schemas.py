from __future__ import annotations

import json

from aidlc_v2_engine.audit import validate_event
from aidlc_v2_engine.catalog import STAGE_SLUGS, UPSTREAM_BASELINE
from aidlc_v2_engine.demo import run_demo
from aidlc_v2_engine.models import HARD_DENIED_AGENT_OPERATIONS, validate_state
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.policy import validate_policy

from tests.support import ROOT, WorkspaceTestCase


class SchemaAndFixtureTests(WorkspaceTestCase):
    def load_schema(self, name: str) -> dict[str, object]:
        return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))

    def test_schema_documents_are_json_objects(self) -> None:
        for name in (
            "policy.schema.json",
            "project-state.schema.json",
            "audit-event.schema.json",
        ):
            with self.subTest(name=name):
                schema = self.load_schema(name)
                self.assertEqual(schema["type"], "object")
                self.assertTrue(str(schema["$id"]).startswith("urn:aidlc-v2-engine:"))

    def test_schema_references_are_local(self) -> None:
        for path in sorted((ROOT / "schemas").glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            references: list[object] = []

            def collect(node: object) -> None:
                if isinstance(node, dict):
                    for key, item in node.items():
                        if key == "$ref":
                            references.append(item)
                        collect(item)
                elif isinstance(node, list):
                    for item in node:
                        collect(item)

            collect(value)
            self.assertTrue(
                all(str(reference).startswith("#/") for reference in references)
            )

    def test_strict_policy_fixture_passes_runtime_validation(self) -> None:
        fixture = json.loads(
            (ROOT / "examples" / "policy.strict.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_policy(fixture)["schema_version"], 2)

    def test_policy_schema_preserves_hard_denials(self) -> None:
        schema = self.load_schema("policy.schema.json")
        properties = schema["properties"]["agent_permissions"]["properties"]  # type: ignore[index]
        for operation in HARD_DENIED_AGENT_OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIs(properties[operation]["const"], False)  # type: ignore[index]

    def test_state_schema_stage_enum_matches_catalog(self) -> None:
        schema = self.load_schema("project-state.schema.json")
        stage_enum = schema["$defs"]["stage"]["enum"]  # type: ignore[index]
        self.assertEqual(stage_enum, list(STAGE_SLUGS))

    def test_generated_demo_state_and_events_validate(self) -> None:
        store = self.workspace / "demo"
        result = run_demo(store)
        repository = JsonProjectRepository(store)
        state = repository.load()
        validate_state(state)
        self.assertEqual(state["workflow"]["status"], "completed")
        events = repository.list_events()
        for event in events:
            validate_event(event)
        self.assertEqual(len(events), result["event_count"])

    def test_nested_state_definitions_reject_extra_fields(self) -> None:
        schema = self.load_schema("project-state.schema.json")
        for name in (
            "project",
            "workflow",
            "stageRecord",
            "artifact",
            "gate",
            "question",
            "sensor",
            "review",
            "unit",
            "learning",
        ):
            with self.subTest(name=name):
                self.assertIs(
                    schema["$defs"][name]["additionalProperties"],  # type: ignore[index]
                    False,
                )

    def test_catalog_resources_pin_the_current_v2_branch(self) -> None:
        self.assertEqual(UPSTREAM_BASELINE["branch"], "v2")
        self.assertEqual(UPSTREAM_BASELINE["framework_version"], "2.6.124")
        self.assertEqual(
            UPSTREAM_BASELINE["commit"],
            "82d2e304206ca352ba3dc140dcbe8b9fb0b13b3d",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
