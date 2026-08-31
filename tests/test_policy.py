from __future__ import annotations

import copy
import unittest

from aidlc_v2_engine.catalog import (
    DOMAIN_AGENTS,
    SCOPES,
    STAGES,
    active_stage_slugs,
    detect_scope,
    required_outputs,
)
from aidlc_v2_engine.errors import ValidationError
from aidlc_v2_engine.models import Actor, HARD_DENIED_AGENT_OPERATIONS
from aidlc_v2_engine.policy import default_policy, validate_policy


class CatalogTests(unittest.TestCase):
    def test_catalog_matches_current_v2_counts(self) -> None:
        self.assertEqual(len(STAGES), 33)
        self.assertEqual(len(SCOPES), 11)
        self.assertEqual(len(DOMAIN_AGENTS), 11)
        self.assertEqual(
            {scope: len(active_stage_slugs(scope)) for scope in SCOPES},
            {
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
            },
        )

    def test_scope_detection_surfaces_ambiguity(self) -> None:
        detection = detect_scope("Fix a CVE vulnerability in broken infrastructure")
        self.assertTrue(detection.needs_composition)
        self.assertIn("security-patch", detection.matched_scopes)
        self.assertIn("bugfix", detection.matched_scopes)
        self.assertIn("infra", detection.matched_scopes)

    def test_scope_detection_defaults_to_classic(self) -> None:
        detection = detect_scope("Add customer notification preferences")
        self.assertEqual(detection.scope, "classic")
        self.assertFalse(detection.needs_composition)

    def test_rich_freeform_intent_requires_composition(self) -> None:
        detection = detect_scope(
            "Add customer notification preferences with auditing and migration support"
        )
        self.assertEqual(detection.scope, "classic")
        self.assertTrue(detection.needs_composition)

    def test_unit_kind_prunes_outputs(self) -> None:
        self.assertEqual(required_outputs("functional-design", "packaging"), ())
        self.assertEqual(
            required_outputs("functional-design", "ui"),
            ("functional-spec", "traceability"),
        )
        self.assertIn(
            "security-requirements",
            required_outputs("nfr-requirements", "packaging"),
        )


class PolicyTests(unittest.TestCase):
    def test_default_policy_is_valid(self) -> None:
        self.assertEqual(validate_policy(default_policy())["schema_version"], 2)

    def test_human_gates_cannot_be_disabled(self) -> None:
        policy = default_policy()
        policy["gates"]["require_human_for_non_initialization"] = False
        with self.assertRaises(ValidationError) as context:
            validate_policy(policy)
        self.assertEqual(context.exception.code, "unsafe_gate_policy")

    def test_walking_skeleton_gate_cannot_be_disabled(self) -> None:
        policy = default_policy()
        policy["construction"]["first_bolt_gated"] = False
        with self.assertRaises(ValidationError) as context:
            validate_policy(policy)
        self.assertEqual(context.exception.code, "unsafe_construction_policy")

    def test_hard_denied_agent_operations_stay_false(self) -> None:
        for operation in HARD_DENIED_AGENT_OPERATIONS:
            policy = copy.deepcopy(default_policy())
            policy["agent_permissions"][operation] = True
            with self.assertRaises(ValidationError):
                validate_policy(policy)

    def test_agent_cannot_claim_governance_role(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Actor("agent_builder", "agent", ("workflow_owner",))
        self.assertEqual(context.exception.code, "agent_governance_role_forbidden")


if __name__ == "__main__":
    unittest.main()
