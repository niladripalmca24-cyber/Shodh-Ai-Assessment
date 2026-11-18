from __future__ import annotations
import glob
import json
import os
import sys
import pytest
import z3

# Set up paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from reviewer.approvals import resolve_effective_requirements
from reviewer.dsl import (
    RestrictedPythonParser,
    dsl_to_z3,
    normalize_time_to_seconds,
    parse_dsl_condition,
)
from reviewer.engine import ReviewEngine
from reviewer.guardrails import GroundingGate, SafeModelExecutor, compute_content_hash
from reviewer.model_client import FakeModelClient
from reviewer.schemas import (
    ApprovalRecord,
    ApprovalStatus,
    Location,
    ReviewBundle,
    Severity,
    SourceRequirement,
    SpecificationRule,
    VerdictStatus,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from reviewer.verifier import SymbolicDecisionDomain, Z3Verifier


# =====================================================================
# Unit Tests: DSL & Time Units
# =====================================================================
class TestDSLAndUnits:
    def test_time_unit_normalization(self):
        assert normalize_time_to_seconds("30 minutes") == 1800
        assert normalize_time_to_seconds("25m") == 1500
        assert normalize_time_to_seconds("1 hour") == 3600
        assert normalize_time_to_seconds("45 seconds") == 45
        assert normalize_time_to_seconds("1800") == 1800

    def test_dsl_parsing_comparisons(self):
        ast_node = parse_dsl_condition("wait_seconds >= 30 minutes")
        domain = SymbolicDecisionDomain()
        z_expr = dsl_to_z3(ast_node, domain.vars_dict)
        assert z_expr is not None

    def test_de_morgan_logical_equivalence(self):
        """Proves ¬(wait < 1500) ⇔ wait >= 1500 via Z3."""
        domain = SymbolicDecisionDomain()
        ast1 = parse_dsl_condition("not (wait_seconds < 1500)")
        ast2 = parse_dsl_condition("wait_seconds >= 1500")
        
        z1 = dsl_to_z3(ast1, domain.vars_dict)
        z2 = dsl_to_z3(ast2, domain.vars_dict)
        
        solver = z3.Solver()
        solver.add(domain.wait_seconds >= 0)
        solver.add(z1 != z2)
        assert solver.check() == z3.unsat, "De Morgan formulations must be formally equivalent"


# =====================================================================
# Unit Tests: Approvals & Trust Boundary
# =====================================================================
class TestApprovals:
    def test_unapproved_change_ignored(self):
        reqs = [
            SourceRequirement(
                id="R3", title="Escalation", description="wait >= 30m", order=3,
                condition_dsl="wait_seconds >= 1800", target_queue="escalation",
                location=Location(artifact_id="doc.md", location="doc:line_12"),
            )
        ]
        unapproved = [
            ApprovalRecord(
                id="APP_01", target_rule_id="R3", attribute="threshold",
                old_value="1800", new_value="1500", status=ApprovalStatus.UNAPPROVED,
                author="intern@shodh.ai", timestamp="2026-11-10T00:00:00Z",
                location=Location(artifact_id="app.json", location="rec:1"),
            )
        ]
        effective, findings, has_conflict = resolve_effective_requirements(reqs, unapproved)
        assert not has_conflict
        assert effective[0].condition_dsl == "wait_seconds >= 1800"

    def test_contradictory_approvals_detection(self):
        reqs = [
            SourceRequirement(
                id="R3", title="Escalation", description="wait >= 30m", order=3,
                condition_dsl="wait_seconds >= 1800", target_queue="escalation",
                location=Location(artifact_id="doc.md", location="doc:line_12"),
            )
        ]
        conflicting = [
            ApprovalRecord(
                id="APP_01", target_rule_id="R3", attribute="threshold",
                old_value="1800", new_value="1500", status=ApprovalStatus.APPROVED,
                revision=2, sequence_order=1, author="lead1@shodh.ai", timestamp="2026-11-10T10:00:00Z",
                location=Location(artifact_id="app.json", location="rec:1"),
            ),
            ApprovalRecord(
                id="APP_02", target_rule_id="R3", attribute="threshold",
                old_value="1800", new_value="1200", status=ApprovalStatus.APPROVED,
                revision=2, sequence_order=2, author="lead2@shodh.ai", timestamp="2026-11-10T10:05:00Z",
                location=Location(artifact_id="app.json", location="rec:2"),
            ),
        ]
        effective, findings, has_conflict = resolve_effective_requirements(reqs, conflicting)
        assert has_conflict is True
        assert any(f.id == "CONTRADICTORY_APPROVAL" for f in findings)


# =====================================================================
# Unit Tests: Restricted Python AST Parser
# =====================================================================
class TestRestrictedPython:
    def test_safe_pure_function(self):
        code = """def route_ticket(ticket):
    if ticket.get('category') is None:
        return 'manual_review'
    if ticket.get('urgent') == True:
        return 'priority_queue'
    return 'normal_queue'
"""
        parser = RestrictedPythonParser(code)
        rules, errs = parser.parse()
        assert len(errs) == 0
        assert len(rules) == 3

    def test_disallowed_imports_caught(self):
        code = """import os
def route_ticket(ticket):
    return 'normal_queue'
"""
        parser = RestrictedPythonParser(code)
        rules, errs = parser.parse()
        assert "Import" in parser.unsupported_constructs


# =====================================================================
# Unit Tests: Guardrails & Security
# =====================================================================
class TestGuardrails:
    def test_grounding_gate_strips_hallucinated_ids(self):
        gate = GroundingGate(valid_rule_ids={"R1", "R2", "R3"}, valid_locations={"doc:l1"})
        client = FakeModelClient(mode="invented_rule_id")
        resp = client.review_unstructured("prose text", [])
        grounded, blocked = gate.filter_findings(resp)
        assert blocked == 1
        assert len(grounded) == 0

    def test_cache_key_invalidation_on_change(self):
        bundle1 = {"rules": [{"id": "R1", "val": 1500}]}
        bundle2 = {"rules": [{"id": "R1", "val": 1800}]}
        hash1 = compute_content_hash(bundle1, [], {})
        hash2 = compute_content_hash(bundle2, [], {})
        assert hash1 != hash2, "Content-addressed cache must invalidate upon change"


# =====================================================================
# TWO PRESERVED DEBUGGING REGRESSIONS (Required by Shodh AI Spec)
# =====================================================================
class TestPreservedDebuggingRegressions:
    def test_bug_1_unit_normalization_mismatch(self):
        """
        Bug 1: Failing output flagged '30 minutes == 1800 seconds' as a threshold mismatch.
        Root Cause Diagnosis: Missing unit multiplier in raw DSL comparison caused string comparison
        to claim 30 != 1800.
        Focused Fix: Added canonical second normalization in DSL parser.
        Regression Test: Proves 30 minutes and 1800s compile to identical symbolic value in Z3.
        """
        domain = SymbolicDecisionDomain()
        ast_minutes = parse_dsl_condition("wait_seconds >= 30 minutes")
        ast_seconds = parse_dsl_condition("wait_seconds >= 1800")
        
        z_min = dsl_to_z3(ast_minutes, domain.vars_dict)
        z_sec = dsl_to_z3(ast_seconds, domain.vars_dict)
        
        solver = z3.Solver()
        solver.add(domain.wait_seconds >= 0)
        solver.add(z_min != z_sec)
        assert solver.check() == z3.unsat, "Bug 1 regression: 30 minutes must equal 1800 seconds symbolically"

    def test_bug_2_ordered_precedence_masking(self):
        """
        Bug 2: Per-Rule vs Ordered Precedence Masking.
        Failing output: Independent rule checks passed swapped R2/R3 rules because each rule condition
        matched isolated specs.
        Root Cause Diagnosis: Checking rules in isolation ignores precedence shadowing.
        Focused Fix: Implemented ordered If/Else Z3 decision chain.
        Regression Test: Proves that swapping R2 (urgent) and R3 (wait >= 1800) generates a counterexample
        where an urgent ticket waiting 2400 seconds is misrouted to escalation instead of priority.
        """
        verifier = Z3Verifier()
        # Normal order: R2 (urgent), R3 (wait >= 1800)
        reqs_normal = [
            SourceRequirement(id="R1", title="Cat", description="miss", order=1, condition_dsl="IS_MISSING(category)", target_queue="manual", location=Location(artifact_id="d", location="1")),
            SourceRequirement(id="R2", title="Urg", description="urg", order=2, condition_dsl="urgent == True", target_queue="priority_queue", location=Location(artifact_id="d", location="2")),
            SourceRequirement(id="R3", title="Wait", description="wait", order=3, condition_dsl="wait_seconds >= 1800", target_queue="escalation", location=Location(artifact_id="d", location="3")),
        ]
        # Swapped order: R3 (wait >= 1800), R2 (urgent)
        reqs_swapped = [
            SourceRequirement(id="R1", title="Cat", description="miss", order=1, condition_dsl="IS_MISSING(category)", target_queue="manual", location=Location(artifact_id="d", location="1")),
            SourceRequirement(id="R3", title="Wait", description="wait", order=2, condition_dsl="wait_seconds >= 1800", target_queue="escalation", location=Location(artifact_id="d", location="3")),
            SourceRequirement(id="R2", title="Urg", description="urg", order=3, condition_dsl="urgent == True", target_queue="priority_queue", location=Location(artifact_id="d", location="2")),
        ]

        f_normal, ast_rules = verifier.build_effective_decision_expr(reqs_normal)
        f_swapped, _ = verifier.build_effective_decision_expr(reqs_swapped)

        ce = verifier.check_equivalence_and_counterexample(f_normal, f_swapped, ast_rules)
        assert ce is not None, "Bug 2 regression: Swapped precedence must be caught by Z3"
        # Counterexample ticket must be urgent and waiting >= 1800 seconds
        assert ce["urgent"] is True
        assert ce["wait_seconds"] >= 1800
        assert ce["expected_route"] == "priority_queue"
        assert ce["actual_route"] == "escalation"


# =====================================================================
# End-to-End Tests Across All 14 Bundles
# =====================================================================
class TestEndToEndBundles:
    @pytest.mark.parametrize(
        "bundle_filename,expected_status",
        [
            ("01_valid_baseline.json", VerdictStatus.PASS),
            ("02_valid_unusual_demorgan.json", VerdictStatus.PASS),
            ("03_valid_paired_rename.json", VerdictStatus.PASS),
            ("04_defect_paired_boundary.json", VerdictStatus.CHANGES_REQUIRED),
            ("05_defect_unapproved_change.json", VerdictStatus.CHANGES_REQUIRED),
            ("06_defect_prose_approval.json", VerdictStatus.CHANGES_REQUIRED),
            ("07_defect_missing_r2.json", VerdictStatus.CHANGES_REQUIRED),
            ("08_defect_precedence_swap.json", VerdictStatus.CHANGES_REQUIRED),
            ("09_incomplete_conflict_appr.json", VerdictStatus.INCOMPLETE),
            ("10_incomplete_unsupported_py.json", VerdictStatus.INCOMPLETE),
        ],
    )
    def test_dev_bundles(self, bundle_filename, expected_status):
        path = os.path.join(BASE_DIR, "data", "dev_bundles", bundle_filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bundle = ReviewBundle.model_validate(data)
        engine = ReviewEngine(model_client=FakeModelClient(mode=bundle.prose_metadata.get("simulate_model_mode", "normal")))
        res = engine.review(bundle)
        assert res.status == expected_status

    @pytest.mark.parametrize(
        "bundle_filename,expected_status",
        [
            ("11_holdout_valid_nested_exc.json", VerdictStatus.PASS),
            ("12_holdout_defect_unit_bug.json", VerdictStatus.CHANGES_REQUIRED),
            ("13_holdout_defect_injection.json", VerdictStatus.CHANGES_REQUIRED),
            ("14_holdout_inc_model_trunc.json", VerdictStatus.INCOMPLETE),
        ],
    )
    def test_holdout_bundles(self, bundle_filename, expected_status):
        path = os.path.join(BASE_DIR, "data", "holdout_bundles", bundle_filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bundle = ReviewBundle.model_validate(data)
        engine = ReviewEngine(model_client=FakeModelClient(mode=bundle.prose_metadata.get("simulate_model_mode", "normal")))
        res = engine.review(bundle)
        assert res.status == expected_status
