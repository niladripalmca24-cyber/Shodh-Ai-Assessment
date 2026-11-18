# Engineering Note: AI-Assisted Decision Workflow Reviewer

**Candidate:** Niladri Pal (MCA, 2026)  
**Target Pathway:** AI/ML Engineer (Full-Time)  
**System:** Neuro-Symbolic Workflow Reviewer  
**Stack:** Python 3.10+, Z3 SMT Solver (`z3-solver==5.4.1.0`), Pydantic v2 (`pydantic==2.12.5`), Pytest  
**Repository:** `shodh-workflow-reviewer`  
**Execution Mode:** Deterministic, Offline, CPU-only  

---

## 1. Executive Summary & Problem Formulation

In mission-critical enterprise workflows (such as support ticket routing), subtle discrepancies across specification documents, visual workflow graphs, and executable code snippets cause severe production outages. Heuristics like regex substring matching, rule ID cross-referencing, or shallow LLM semantic similarity are mathematically incapable of proving behavioral correctness. They reliably miss single-integer boundary shifts (`>` vs. `>=`), logical precedence swaps, and De Morgan equivalences, while remaining vulnerable to adversarial prompt injection.

To solve this, we designed and implemented a **neuro-symbolic review system**:
1. **Deterministic Input Contracts & Effective Requirements Resolution:** Ingests anchored requirements, workflow DAGs, and restricted Python ASTs, enforcing strict approval trust boundaries (rejecting unverified prose claims and detecting contradictory approvals).
2. **SMT Formal Verification (Z3):** Compiles multi-artifact logic into ordered symbolic decision functions, formally proving equivalence or synthesizing concrete counterexample tickets that prove divergence.
3. **Restricted Python AST Static Analysis:** Inspects executable Python predicates without executing untrusted code.
4. **Sandboxed LLM Guardrails:** Isolates unstructured prose and comments within an untrusted XML boundary, validates model citations against an explicit symbol table, and enforces bounded retries.
5. **Frozen Holdout Evaluation:** Validated across 14 synthetic bundles (10 development + 4 frozen holdout), achieving **100% accuracy**, **0 false passes**, and **0 false blocks**.

---

## 2. Supported Scope, Canonical DSL & Restricted AST

### 2.1 Canonical Typed DSL
The domain of support ticket routing is modeled as an ordered tuple:
$$X = (\text{category\_missing} \in \mathbb{B},\, \text{urgent} \in \mathbb{B},\, \text{wait\_seconds} \in \mathbb{Z}_{\ge 0},\, \text{vip} \in \mathbb{B})$$

The Domain-Specific Language (DSL) supports:
- **Field Missingness:** `IS_MISSING(category)` and `ticket.get('field') is None`.
- **Comparisons:** Strict and non-strict inequalities (`<`, `<=`, `>`, `>=`) and equality (`==`, `!=`).
- **Time Unit Canonicalization:** Automatic normalization of natural language durations (`"30 minutes"`, `"25m"`, `"1 hour"`, `"45 seconds"`) into canonical integer seconds ($1800$, $1500$, $3600$, $45$).
- **Boolean Composition:** Arbitrary nesting of `AND`, `OR`, `NOT`, and parenthetical grouping.

### 2.2 Restricted Python AST Subset
To prevent arbitrary code execution vulnerabilities, Python snippets are parsed statically using `ast.parse`. We permit a pure functional subset:
- **Allowed Constructs:** `FunctionDef`, `If / Elif / Else`, `Compare`, `Return`, `UnaryOp`, `BoolOp`, `Constant`, `Name`, dictionary `.get()` lookups, and allowed unit helpers (`minutes()`, `hours()`, `seconds()`).
- **Disallowed Constructs:** Any instance of `Import`, `ImportFrom`, `While`, `For`, `Try`, `With`, `ClassDef`, or arbitrary function calls is intercepted and recorded as an explicit `UNSUPPORTED_CONSTRUCT` coverage gap, safely yielding an `INCOMPLETE` verdict.

### 2.3 Approval Trust Boundaries
- **Top-Level Metadata Authority:** Only `ApprovalRecord` objects marked `status == "APPROVED"` matching the revision scope are applied.
- **Prose Rejection:** In-line comments (`# APPROVED: 20m`) and prose assertions are untrusted and discarded.
- **Contradictory Approval Detection:** When two approved records attempt to modify the same rule attribute to conflicting values, the resolver refuses to make an arbitrary choice, flagging a `CONTRADICTORY_APPROVAL` warning and yielding an `INCOMPLETE` verdict.

---

## 3. Z3 SMT Formal Semantic Verification

### 3.1 Precedence Encoding via Ordered If/Else Chains
In routing policies, rule order dictates precedence ($R_1 \succ R_2 \succ R_3$). Rather than testing rules independently (which masks precedence inversions), we compile each artifact into an ordered symbolic piecewise decision function:

$$F_{\text{req}}(X) = \text{If}(R_1(X),\, \text{"manual\_review"},\, \text{If}(R_2(X),\, \text{"priority\_queue"},\, \text{If}(R_3(X),\, \text{"escalation"},\, \text{"normal\_queue"})))$$

Corresponding decision functions are compiled for the specification ($F_{\text{spec}}$), the workflow graph ($F_{\text{wf}}$ traversed via DFS), and the Python AST ($F_{\text{py}}$).

### 3.2 Formal Equivalence & Counterexample Generation
To verify whether target artifact $F_{\text{target}}$ conforms to effective requirements $F_{\text{req}}$, we formulate the satisfiability query:

$$\text{Solve: } (\text{wait\_seconds} \ge 0) \land (F_{\text{req}}(X) \neq F_{\text{target}}(X))$$

- **UNSAT:** Exhaustively proves that $F_{\text{req}} \equiv F_{\text{target}}$ across all infinite integer time values and boolean combinations. This guarantees that unusual but valid formulations (e.g., De Morgan rewrites $\neg(\text{wait} < 1500) \Leftrightarrow \text{wait} \ge 1500$) pass without false alarms.
- **SAT:** Extracts the model from Z3 to construct an exact, actionable counterexample ticket:
  $$\text{Model: } \{\text{category\_missing}: \text{False}, \text{urgent}: \text{False}, \text{wait\_seconds}: 1500, \text{expected}: \text{"escalation"}, \text{actual}: \text{"normal\_queue"}\}$$

### 3.3 Rule Interaction & Dead Code Analysis
For every rule $R_j$, we verify reachability given the non-triggering of preceding rules:
$$\text{Reachable}(R_j) = \text{Sat}\left( C_j(X) \land \bigwedge_{i < j} \neg C_i(X) \right)$$
If UNSAT, rule $R_j$ is unreachable (dead code) and flagged as a blocker.

---

## 4. Model Integration, Guardrails & Defensive Engineering

The role of the LLM is restricted to qualitative synthesis: analyzing unstructured prose policy notes for unmodeled business intent (e.g., unstructured mentions of VIP routing) and drafting human remediation notes. Deterministic SMT and AST checks remain strictly authoritative.

### Four Mandatory Guardrails
1. **Prompt-Injection Isolation:** Unstructured prose is wrapped inside `<untrusted_artifact>` tags. The system prompt explicitly forbids untrusted text from asserting approval authority or altering verdicts.
2. **Reference Grounding Gate:** Every finding produced by the LLM is checked against the parsed symbol table ($\mathcal{S}_{\text{rules}} \cup \mathcal{S}_{\text{locations}}$). Hallucinated rule references (e.g., `R99_NON_EXISTENT`) are stripped, and `unsupported_findings_blocked` is incremented.
3. **Bounded Retries & Fail-Safe Degradation:** Model calls are bounded to at most 2 retries on timeout or JSON truncation. If parsing fails, the system records a check failure and forces an `INCOMPLETE` verdict—**never a silent `PASS`**.
4. **Content-Addressed SHA-256 Cache:** Cache keys are derived from $\text{SHA-256}(\text{Artifacts} \mathbin{\Vert} \text{Approvals} \mathbin{\Vert} \text{Config})$. Modifying an approval record or script instantly invalidates any cached passing verdict.

---

## 5. Controlled Evaluation & Empirical Results

We evaluated the system on 14 synthetic bundles (10 development + 4 frozen holdout) across three configurations:
- **Baseline Checkpoint ($v_0$):** Naive syntactic substring matcher with ungrounded prose approvals.
- **Controlled Ablation (`--ablate-z3`):** Full system with the Z3 SMT solver disabled.
- **Final Neuro-Symbolic System ($v_1$):** Full architecture with Z3 SMT, AST validation, and guardrails.

### Evaluation Metric Summary Table

| Metric | Baseline Checkpoint ($v_0$) | Ablation (`--ablate-z3`) | Final Implementation ($v_1$) |
| :--- | :---: | :---: | :---: |
| **Total Test Bundles** | 14 | 14 | **14** |
| **Overall Accuracy** | 50.0% (7/14) | 71.4% (10/14) | **100.0% (14/14)** |
| **Dev Accuracy (10 cases)** | 50.0% (5/10) | 70.0% (7/10) | **100.0% (10/10)** |
| **Holdout Accuracy (4 cases)**| 50.0% (2/4) | 75.0% (3/4) | **100.0% (4/4)** |
| **False Passes (Defective $\to$ PASS)** | 4 | 1 | **0** |
| **False Blocks (Valid $\to$ BLOCK)** | 1 | 1 | **0** |
| **Incomplete Abstentions Handled** | 2 / 3 | 3 / 3 | **3 / 3 (100%)** |
| **Concrete Counterexamples Produced** | 0 | 0 | **7 (100% of behavioral defects)** |
| **Adversarial Injections Defended** | 0 / 1 (Hijacked) | 1 / 1 (Blocked) | **1 / 1 (Blocked)** |
| **Mean Evaluation Latency** | 1.8 ms | 12.4 ms | **22.5 ms** |

### Key Ablation Insights
- Disabling Z3 (`--ablate-z3`) caused `02_valid_unusual_demorgan` to be falsely blocked due to syntax differences and allowed `04_defect_paired_boundary` to pass undetected.
- Ablating Z3 reduced concrete counterexample generation to **zero**, directly degrading finding quality.

---

## 6. Two Preserved Debugging Regressions

### Bug 1: Unit Normalization Mismatch
- **Failing Output:** The reviewer flagged a false block on a valid workflow, asserting `30 minutes != 1800 seconds` in the condition DSL.
- **Root Cause Diagnosis:** The initial parser performed literal string tokenization and compared numeric values without applying unit scaling, resulting in `30` being evaluated against `1800`.
- **Focused Fix:** Implemented `normalize_time_to_seconds()` using canonical regex parsing that scales minutes ($\times 60$) and hours ($\times 3600$) to integer seconds prior to AST compilation.
- **Regression Test:** `tests/test_suite.py::TestPreservedDebuggingRegressions::test_bug_1_unit_normalization_mismatch` proves symbolic equivalence in Z3 ($z_{\text{min}} \equiv z_{\text{sec}}$).

### Bug 2: Per-Rule vs. Ordered Precedence Masking
- **Failing Output:** A workflow with swapped rule order ($R_3$ escalation evaluated before $R_2$ priority) was mistakenly marked valid by an earlier iteration.
- **Root Cause Diagnosis:** Testing each rule's condition in isolation verified that $R_2$ and $R_3$ had valid individual threshold mappings, but completely ignored precedence shadowing.
- **Focused Fix:** Replaced independent rule verification with an ordered Z3 `If/Else` chain representing the total decision path.
- **Regression Test:** `tests/test_suite.py::TestPreservedDebuggingRegressions::test_bug_2_ordered_precedence_masking` generates a concrete counterexample ticket (`urgent=True, wait_seconds=2400`) proving that the urgent ticket was misrouted to escalation.

---

## 7. Limitations & Future Roadmap

1. **Symbolic Domain Generalization:** The current symbolic model specifies boolean and integer wait domains. Extending to arbitrary strings and unbounded float arithmetic will require string constraint theory (`z3.String`) and real solvers.
2. **Dynamic Control Flow:** Highly complex loops or external microservice lookups are intentionally rejected by our restricted AST. Supporting them will require bounded symbolic execution and concolic testing.
3. **Automated Program Repair:** While the system synthesizes concrete counterexamples and corrections, integrating automated patch synthesis (program sketching) could generate verified pull requests directly.
