from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Set
import z3

from reviewer.approvals import resolve_effective_requirements
from reviewer.guardrails import SafeModelExecutor, compute_content_hash
from reviewer.model_client import FakeModelClient, ModelClient
from reviewer.schemas import (
    CoverageReport,
    Finding,
    Location,
    ReviewBundle,
    ReviewResult,
    Severity,
    SourceRequirement,
    VerdictStatus,
    WorkflowNodeType,
)
from reviewer.verifier import Z3Verifier


class ReviewEngine:
    """
    Cumulative decision engine coordinating Stage 1 (contracts & approvals),
    Stage 2 (Z3 semantic verification), Stage 3 (model guardrails & failure modes),
    and Stage 4 (verdict reporting).
    """

    def __init__(
        self,
        model_client: Optional[ModelClient] = None,
        ablate_z3: bool = False,
    ):
        self.model_client = model_client or FakeModelClient()
        self.ablate_z3 = ablate_z3

    def review(self, bundle: ReviewBundle) -> ReviewResult:
        start_time = time.time()
        findings: List[Finding] = []
        check_results: Dict[str, bool] = {}
        coverage_reasons: List[str] = []
        unsupported_constructs: List[str] = []
        unreviewed_rules: List[str] = []

        # -------------------------------------------------------------
        # Stage 1: Ingestion, Approvals & Effective Requirements
        # -------------------------------------------------------------
        effective_reqs, approval_findings, has_conflict = resolve_effective_requirements(
            bundle.source_requirements, bundle.approval_records
        )
        findings.extend(approval_findings)
        check_results["approval_conflict_check"] = not has_conflict

        if has_conflict:
            # Contradictory approvals prevent establishing effective requirements
            coverage_reasons.append("Contradictory approved records prevent determining canonical requirements.")

        # Symbol table of valid IDs and locations
        symbol_rule_ids: Set[str] = {r.id for r in bundle.source_requirements}
        symbol_rule_ids.update({r.id for r in bundle.specification_rules})
        symbol_locations: Set[str] = {
            r.location.location for r in bundle.source_requirements
        }
        symbol_locations.update({r.location.location for r in bundle.specification_rules})
        symbol_locations.update({n.location.location for n in bundle.workflow_graph.nodes.values()})
        symbol_locations.add(bundle.python_snippet.location.location)

        # Check for unapproved changes being wrongfully implemented
        unapproved_records = [
            r for r in bundle.approval_records if r.status.value == "UNAPPROVED"
        ]

        # -------------------------------------------------------------
        # Stage 2: Deterministic Semantic Verification via Z3 SMT
        # -------------------------------------------------------------
        verifier = Z3Verifier(ablate_z3=self.ablate_z3)
        missing_req_ids = []

        if not has_conflict:
            # 1. Missing requirements check: check if all effective reqs exist in spec
            spec_rule_ids = {s.id for s in bundle.specification_rules}
            for req in effective_reqs:
                if req.id not in spec_rule_ids:
                    missing_req_ids.append(req.id)
                    findings.append(
                        Finding(
                            id=f"MISSING_RULE_{req.id}",
                            severity=Severity.BLOCKER,
                            rule_ref=req.id,
                            artifact_location=req.location,
                            description=f"Requirement '{req.id}' is missing from specification and workflow.",
                            supporting_evidence=f"Requirement {req.id} ({req.description}) is present in effective requirements but omitted from specification rules.",
                            suggested_correction=f"Add specification rule and workflow node for {req.id}.",
                        )
                    )
            check_results["spec_coverage_check"] = len(missing_req_ids) == 0

            # Build decision expressions
            f_req, ast_req_rules = verifier.build_effective_decision_expr(effective_reqs)
            f_spec, _ = verifier.build_spec_decision_expr(bundle.specification_rules)
            f_wf, visited_nodes, wf_errors = verifier.build_workflow_decision_expr(bundle.workflow_graph)
            
            # Check for unreachable nodes or graph errors
            all_wf_nodes = set(bundle.workflow_graph.nodes.keys())
            unreachable = all_wf_nodes - visited_nodes
            if unreachable:
                findings.append(
                    Finding(
                        id="UNREACHABLE_WORKFLOW_NODES",
                        severity=Severity.BLOCKER,
                        artifact_location=bundle.workflow_graph.nodes[next(iter(unreachable))].location,
                        description=f"Workflow graph contains unreachable nodes: {sorted(unreachable)}",
                        supporting_evidence=f"Nodes {sorted(unreachable)} cannot be reached from entry node '{bundle.workflow_graph.entry_node_id}'.",
                        suggested_correction="Connect or prune orphaned workflow nodes.",
                    )
                )
            if wf_errors:
                for w_err in wf_errors:
                    findings.append(
                        Finding(
                            id="WORKFLOW_GRAPH_ERROR",
                            severity=Severity.BLOCKER,
                            description=w_err,
                            supporting_evidence="Structural flaw in workflow graph.",
                        )
                    )

            # Python Snippet Parsing & AST Check
            f_py, py_unsupported, py_errors = verifier.build_python_decision_expr(bundle.python_snippet)
            if py_unsupported:
                unsupported_constructs.extend(py_unsupported)
                coverage_reasons.append(
                    f"Python snippet contains unsupported/disallowed constructs: {py_unsupported}"
                )
                findings.append(
                    Finding(
                        id="UNSUPPORTED_PYTHON_AST",
                        severity=Severity.WARNING,
                        artifact_location=bundle.python_snippet.location,
                        description=f"Python code contains unsupported AST constructs: {py_unsupported}",
                        supporting_evidence="Static AST analysis detected constructs outside the restricted safe subset.",
                        suggested_correction="Refactor Python snippet into pure if/elif/else expressions without external imports or dynamic loops.",
                    )
                )
            if py_errors and not py_unsupported:
                findings.append(
                    Finding(
                        id="PYTHON_PARSE_ERROR",
                        severity=Severity.BLOCKER,
                        artifact_location=bundle.python_snippet.location,
                        description=f"Failed to parse Python snippet: {py_errors}",
                        supporting_evidence=str(py_errors),
                    )
                )

            # Formal Equivalence Verification (Z3 vs Ablated)
            if self.ablate_z3:
                # Ablated mode: naive string comparison of conditions
                check_results["z3_spec_equivalence"] = False
                check_results["z3_wf_equivalence"] = False
                check_results["z3_py_equivalence"] = False
                
                # Naive match
                spec_matches = len(bundle.specification_rules) == len(effective_reqs)
                for r, s in zip(effective_reqs, bundle.specification_rules):
                    if r.condition_dsl != s.condition_dsl:
                        spec_matches = False
                        findings.append(
                            Finding(
                                id="ABLATED_SYNTACTIC_MISMATCH",
                                severity=Severity.BLOCKER,
                                rule_ref=r.id,
                                description=f"Condition string mismatch for {r.id}: '{r.condition_dsl}' vs '{s.condition_dsl}'",
                                supporting_evidence="Naive string equality check failed.",
                            )
                        )
            else:
                # Z3 Formal Verification: Requirements vs Specification
                if check_results.get("spec_coverage_check", False):
                    ce_spec = verifier.check_equivalence_and_counterexample(f_req, f_spec, ast_req_rules)
                    if ce_spec:
                        findings.append(
                            Finding(
                                id="SPEC_SEMANTIC_MISMATCH",
                                severity=Severity.BLOCKER,
                                artifact_location=bundle.specification_rules[0].location if bundle.specification_rules else None,
                                description="Specification does not implement effective requirements correctly.",
                                supporting_evidence=(
                                    f"For ticket input: {ce_spec}, expected route is '{ce_spec['expected_route']}' "
                                    f"but specification routes to '{ce_spec['actual_route']}'."
                                ),
                                suggested_correction="Update specification conditions or rule order.",
                                counterexample_ticket=ce_spec,
                            )
                        )
                        check_results["z3_spec_equivalence"] = False
                    else:
                        check_results["z3_spec_equivalence"] = True

                # Z3 Formal Verification: Requirements vs Workflow Graph
                ce_wf = verifier.check_equivalence_and_counterexample(f_req, f_wf, ast_req_rules)
                if ce_wf:
                    findings.append(
                        Finding(
                            id="WORKFLOW_SEMANTIC_MISMATCH",
                            severity=Severity.BLOCKER,
                            artifact_location=Location(artifact_id="workflow_graph", location="branch_logic"),
                            description="Workflow graph logic diverges from effective requirements.",
                            supporting_evidence=(
                                f"Counterexample ticket: {ce_wf}. Expected route: '{ce_wf['expected_route']}', "
                                f"Workflow route: '{ce_wf['actual_route']}'."
                            ),
                            suggested_correction="Review workflow decision branching and precedence.",
                            counterexample_ticket=ce_wf,
                        )
                    )
                    check_results["z3_wf_equivalence"] = False
                else:
                    check_results["z3_wf_equivalence"] = True

                # Z3 Formal Verification: Requirements vs Python Snippet (if AST allowed)
                if f_py is not None:
                    ce_py = verifier.check_equivalence_and_counterexample(f_req, f_py, ast_req_rules)
                    if ce_py:
                        findings.append(
                            Finding(
                                id="PYTHON_SCRIPT_DIVERGENCE",
                                severity=Severity.BLOCKER,
                                artifact_location=bundle.python_snippet.location,
                                description="Python routing implementation disagrees with effective requirements.",
                                supporting_evidence=(
                                    f"Counterexample ticket: {ce_py}. Expected route: '{ce_py['expected_route']}', "
                                    f"Python routed to: '{ce_py['actual_route']}'."
                                ),
                                suggested_correction="Update Python if/elif logic and threshold constants.",
                                counterexample_ticket=ce_py,
                            )
                        )
                        check_results["z3_py_equivalence"] = False
                    else:
                        check_results["z3_py_equivalence"] = True

                # Rule interaction & shadowing check
                shadow_findings = verifier.check_rule_shadowing_and_dead_code(effective_reqs)
                findings.extend(shadow_findings)

        # -------------------------------------------------------------
        # Stage 3: Model Client Inspection, Guardrails & Attack Defense
        # -------------------------------------------------------------
        prose_text = str(bundle.prose_metadata.get("unstructured_text", ""))
        
        # Configure model client mode if bundle specifies simulated failure mode
        active_client = self.model_client
        sim_mode = bundle.prose_metadata.get("simulate_model_mode")
        if sim_mode and isinstance(self.model_client, FakeModelClient):
            active_client = FakeModelClient(mode=sim_mode)

        safe_executor = SafeModelExecutor(active_client, max_retries=2)
        
        req_dicts = [r.model_dump() for r in effective_reqs]
        (
            model_resp,
            grounded_findings,
            blocked_count,
            model_failure,
        ) = safe_executor.execute_with_guardrails(
            prose_text, req_dicts, symbol_rule_ids, symbol_locations
        )

        findings.extend(grounded_findings)
        check_results["model_inspection_clean"] = not model_failure

        if model_failure:
            coverage_reasons.append("Model execution failed after bounded retries (timeout or malformed JSON).")

        # Check for adversarial prompt injection in prose
        if "IGNORE" in prose_text.upper() and ("PASS" in prose_text.upper() or "OVERRIDE" in prose_text.upper()):
            findings.append(
                Finding(
                    id="PROMPT_INJECTION_DETECTED",
                    severity=Severity.WARNING,
                    artifact_location=Location(artifact_id="prose_metadata", location="doc:prose"),
                    description="Detected untrusted prompt injection instructions inside requirement text.",
                    supporting_evidence=f"Text matched adversarial pattern: '{prose_text}'. Reviewer authority preserved.",
                    suggested_correction="Sanitize input text and remove meta-instructions.",
                )
            )

        # -------------------------------------------------------------
        # Stage 4: Cumulative Decision Orchestration & Verdict
        # -------------------------------------------------------------
        blockers = [f for f in findings if f.severity == Severity.BLOCKER]
        
        # Compute coverage
        verified_rules = []
        for req in effective_reqs:
            if req.id not in missing_req_ids and not any(f.rule_ref == req.id and f.severity == Severity.BLOCKER for f in findings):
                verified_rules.append(req.id)
            else:
                unreviewed_rules.append(req.id)

        total_rules = max(len(effective_reqs), 1)
        cov_percent = (len(verified_rules) / total_rules) * 100.0

        # Strict Verdict Rules:
        # 1. CHANGES_REQUIRED: >= 1 evidenced deterministic blocker exists.
        # 2. INCOMPLETE: 0 blockers, AND >= 1 coverage gap / unreviewed scope (contradictory approvals, unsupported AST, missing evidence, model failure).
        # 3. PASS: 0 blockers AND 100% verified.
        if len(blockers) > 0:
            status = VerdictStatus.CHANGES_REQUIRED
            summary = f"Review failed with {len(blockers)} blocking defect(s). Remediations required."
        elif has_conflict or len(unsupported_constructs) > 0 or model_failure:
            status = VerdictStatus.INCOMPLETE
            summary = (
                f"Review is incomplete due to coverage gap / unreviewed scope: "
                f"{'; '.join(coverage_reasons)}"
            )
        elif cov_percent < 100.0:
            status = VerdictStatus.INCOMPLETE
            summary = f"Incomplete review: only {cov_percent:.1f}% coverage established without blockers."
        else:
            status = VerdictStatus.PASS
            summary = "All effective requirements formally verified across specification, workflow graph, and Python implementation."

        coverage_report = CoverageReport(
            total_rules=total_rules,
            verified_rules=verified_rules,
            unreviewed_rules=unreviewed_rules,
            coverage_percent=cov_percent,
            unsupported_constructs=unsupported_constructs,
            reasons=coverage_reasons,
        )

        content_hash = compute_content_hash(
            bundle.model_dump(),
            [r.model_dump() for r in bundle.approval_records],
            {"model_id": getattr(self.model_client, "model_id", "none"), "ablate_z3": self.ablate_z3},
        )

        provenance = {
            "content_hash_sha256": content_hash,
            "ablate_z3": self.ablate_z3,
            "blocked_hallucinated_findings": blocked_count,
            "execution_time_ms": (time.time() - start_time) * 1000,
        }

        return ReviewResult(
            bundle_id=bundle.bundle_id,
            status=status,
            summary=summary,
            findings=findings,
            coverage=coverage_report,
            effective_requirements=[r.model_dump() for r in effective_reqs],
            check_results=check_results,
            provenance=provenance,
        )
