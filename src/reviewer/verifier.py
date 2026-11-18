from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
import z3

from reviewer.dsl import (
    ASTNode,
    Const,
    RestrictedPythonParser,
    dsl_to_z3,
    eval_dsl,
    parse_dsl_condition,
)
from reviewer.schemas import (
    Finding,
    Location,
    PythonSnippet,
    Severity,
    SourceRequirement,
    SpecificationRule,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)


class SymbolicDecisionDomain:
    def __init__(self):
        self.category_missing = z3.Bool("category_missing")
        self.urgent = z3.Bool("urgent")
        self.wait_seconds = z3.Int("wait_seconds")
        self.vip = z3.Bool("vip")

    @property
    def vars_dict(self) -> Dict[str, Any]:
        return {
            "category_missing": self.category_missing,
            "urgent": self.urgent,
            "wait_seconds": self.wait_seconds,
            "vip": self.vip,
            # Common synonyms in conditions
            "category": self.category_missing,
        }

    def domain_constraints(self) -> List[z3.ExprRef]:
        return [self.wait_seconds >= 0]


class Z3Verifier:
    def __init__(self, ablate_z3: bool = False):
        self.ablate_z3 = ablate_z3
        self.domain = SymbolicDecisionDomain()

    def build_effective_decision_expr(
        self, reqs: List[SourceRequirement], default_queue: str = "normal_queue"
    ) -> Tuple[z3.ExprRef, List[Tuple[ASTNode, str]]]:
        """
        Builds an ordered If/Else expression from effective requirements.
        Returns (Z3_expression, List[(ast_node, queue_str)]).
        """
        ast_rules: List[Tuple[ASTNode, str]] = []
        for req in sorted(reqs, key=lambda r: r.order):
            cond_ast = parse_dsl_condition(req.condition_dsl)
            ast_rules.append((cond_ast, req.target_queue))

        expr = z3.StringVal(default_queue)
        for cond_ast, queue in reversed(ast_rules):
            z3_cond = dsl_to_z3(cond_ast, self.domain.vars_dict)
            expr = z3.If(z3_cond, z3.StringVal(queue), expr)
        return expr, ast_rules

    def build_spec_decision_expr(
        self, spec_rules: List[SpecificationRule], default_queue: str = "normal_queue"
    ) -> Tuple[z3.ExprRef, List[Tuple[ASTNode, str]]]:
        ast_rules: List[Tuple[ASTNode, str]] = []
        for rule in sorted(spec_rules, key=lambda r: r.precedence):
            cond_ast = parse_dsl_condition(rule.condition_dsl)
            ast_rules.append((cond_ast, rule.target_queue))

        expr = z3.StringVal(default_queue)
        for cond_ast, queue in reversed(ast_rules):
            z3_cond = dsl_to_z3(cond_ast, self.domain.vars_dict)
            expr = z3.If(z3_cond, z3.StringVal(queue), expr)
        return expr, ast_rules

    def build_workflow_decision_expr(
        self, graph: WorkflowGraph, default_queue: str = "normal_queue"
    ) -> Tuple[z3.ExprRef, Set[str], List[str]]:
        """
        Traverses workflow graph DFS from entry_node_id.
        Returns (z3_expr, visited_nodes, errors).
        """
        visited: Set[str] = set()
        errors: List[str] = []

        if graph.entry_node_id not in graph.nodes:
            errors.append(f"Entry node '{graph.entry_node_id}' not found in workflow nodes.")
            return z3.StringVal(default_queue), visited, errors

        def traverse(node_id: Optional[str]) -> z3.ExprRef:
            if not node_id:
                return z3.StringVal(default_queue)
            if node_id not in graph.nodes:
                errors.append(f"Workflow branch references missing node '{node_id}'")
                return z3.StringVal(default_queue)

            node = graph.nodes[node_id]
            visited.add(node_id)

            if node.node_type == WorkflowNodeType.ACTION:
                queue = node.action_queue or default_queue
                return z3.StringVal(queue)
            elif node.node_type == WorkflowNodeType.CONDITION:
                if not node.condition_dsl:
                    errors.append(f"Condition node '{node_id}' has empty condition_dsl")
                    return z3.StringVal(default_queue)
                cond_ast = parse_dsl_condition(node.condition_dsl)
                z3_cond = dsl_to_z3(cond_ast, self.domain.vars_dict)
                true_branch = traverse(node.next_node_true)
                false_branch = traverse(node.next_node_false)
                return z3.If(z3_cond, true_branch, false_branch)
            else:
                errors.append(f"Unknown node type '{node.node_type}' in node '{node_id}'")
                return z3.StringVal(default_queue)

        expr = traverse(graph.entry_node_id)
        return expr, visited, errors

    def build_python_decision_expr(
        self, snippet: PythonSnippet, default_queue: str = "normal_queue"
    ) -> Tuple[Optional[z3.ExprRef], List[str], List[str]]:
        """
        Parses restricted Python snippet and converts it into Z3 expression.
        Returns (z3_expr, unsupported_constructs, parse_errors).
        """
        parser = RestrictedPythonParser(snippet.code, snippet.function_name)
        rules, errors = parser.parse()
        if parser.unsupported_constructs:
            return None, parser.unsupported_constructs, errors
        if errors:
            return None, [], errors

        expr = z3.StringVal(default_queue)
        for cond_ast, queue in reversed(rules):
            if cond_ast is None:
                # Unconditional return (else branch)
                expr = z3.StringVal(queue)
            else:
                z3_cond = dsl_to_z3(cond_ast, self.domain.vars_dict)
                expr = z3.If(z3_cond, z3.StringVal(queue), expr)

        return expr, [], []

    def check_equivalence_and_counterexample(
        self,
        f_expected: z3.ExprRef,
        f_actual: z3.ExprRef,
        expected_ast_rules: List[Tuple[ASTNode, str]],
        default_queue: str = "normal_queue",
    ) -> Optional[Dict[str, Any]]:
        """
        Uses Z3 to formally prove if f_expected == f_actual over the domain.
        If SAT, returns a concrete counterexample ticket payload.
        If UNSAT, returns None (mathematically equivalent).
        """
        solver = z3.Solver()
        for c in self.domain.domain_constraints():
            solver.add(c)

        solver.add(f_expected != f_actual)

        check_result = solver.check()
        if check_result == z3.sat:
            m = solver.model()
            
            # Extract concrete values
            cat_missing = bool(z3.is_true(m.eval(self.domain.category_missing)))
            urgent_val = bool(z3.is_true(m.eval(self.domain.urgent)))
            wait_val = m.eval(self.domain.wait_seconds).as_long() if m.eval(self.domain.wait_seconds) is not None else 0
            vip_val = bool(z3.is_true(m.eval(self.domain.vip)))

            ticket = {
                "category_missing": cat_missing,
                "category": None if cat_missing else "general",
                "urgent": urgent_val,
                "wait_seconds": wait_val,
                "waiting_time": wait_val,
                "vip": vip_val,
            }

            # Evaluate expected route vs actual route
            expected_route_val = str(m.eval(f_expected)).strip('"')
            actual_route_val = str(m.eval(f_actual)).strip('"')

            ticket["expected_route"] = expected_route_val
            ticket["actual_route"] = actual_route_val
            return ticket

        return None

    def check_rule_shadowing_and_dead_code(
        self, reqs: List[SourceRequirement]
    ) -> List[Finding]:
        """
        Detects unreachable dead rules or shadowed exceptions.
        """
        findings: List[Finding] = []
        accumulated_conditions: List[z3.ExprRef] = []

        for req in sorted(reqs, key=lambda r: r.order):
            cond_ast = parse_dsl_condition(req.condition_dsl)
            z3_cond = dsl_to_z3(cond_ast, self.domain.vars_dict)

            # Check if this rule is reachable given earlier rules haven't fired
            solver = z3.Solver()
            for c in self.domain.domain_constraints():
                solver.add(c)
            for prev_cond in accumulated_conditions:
                solver.add(z3.Not(prev_cond))
            solver.add(z3_cond)

            if solver.check() == z3.unsat:
                findings.append(
                    Finding(
                        id=f"SHADOWED_RULE_{req.id}",
                        severity=Severity.BLOCKER,
                        rule_ref=req.id,
                        artifact_location=req.location,
                        description=f"Rule '{req.id}' is unreachable (dead code) because earlier rules shadow it.",
                        supporting_evidence=(
                            f"Rule condition '{req.condition_dsl}' cannot be satisfied when preceding rules do not trigger."
                        ),
                        suggested_correction="Adjust the precedence order or make the earlier conditions more restrictive.",
                    )
                )

            accumulated_conditions.append(z3_cond)

        return findings
