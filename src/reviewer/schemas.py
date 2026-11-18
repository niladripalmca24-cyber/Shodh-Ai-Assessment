from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


class VerdictStatus(str, Enum):
    PASS = "PASS"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


class Location(BaseModel):
    artifact_id: str = Field(..., description="ID or filename of the artifact")
    version: str = Field(default="1.0", description="Artifact version string")
    location: str = Field(..., description="Line, node or function reference, e.g., 'doc:line_12', 'wf:node_3'")


class SourceRequirement(BaseModel):
    id: str = Field(..., description="Unique rule ID, e.g., 'R1'")
    title: str
    description: str
    order: int = Field(..., description="Precedence rank: lower number = higher precedence")
    condition_dsl: str = Field(..., description="Condition expression in canonical DSL")
    target_queue: str = Field(..., description="Destination queue if condition holds")
    location: Location
    version: str = "1.0"


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    UNAPPROVED = "UNAPPROVED"
    REJECTED = "REJECTED"


class ApprovalRecord(BaseModel):
    id: str
    target_rule_id: str
    attribute: str = Field(..., description="Target attribute modified, e.g., 'threshold', 'condition_dsl'")
    old_value: Any
    new_value: Any
    status: ApprovalStatus = ApprovalStatus.UNAPPROVED
    revision: int = 1
    sequence_order: int = 1
    author: str
    timestamp: str
    location: Location


class SpecificationRule(BaseModel):
    id: str
    title: str
    condition_dsl: str
    target_queue: str
    precedence: int
    location: Location
    version: str = "1.0"


class WorkflowNodeType(str, Enum):
    CONDITION = "condition"
    ACTION = "action"


class WorkflowNode(BaseModel):
    id: str
    node_type: WorkflowNodeType
    condition_dsl: Optional[str] = None
    action_queue: Optional[str] = None
    next_node_true: Optional[str] = None
    next_node_false: Optional[str] = None
    location: Location


class WorkflowGraph(BaseModel):
    version: str = "1.0"
    entry_node_id: str
    nodes: Dict[str, WorkflowNode]


class PythonSnippet(BaseModel):
    version: str = "1.0"
    function_name: str = "route_ticket"
    code: str
    location: Location


class ReviewBundle(BaseModel):
    bundle_id: str
    name: str
    description: str
    source_requirements: List[SourceRequirement]
    specification_rules: List[SpecificationRule]
    workflow_graph: WorkflowGraph
    python_snippet: PythonSnippet
    approval_records: List[ApprovalRecord] = Field(default_factory=list)
    prose_metadata: Dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str
    severity: Severity
    rule_ref: Optional[str] = None
    artifact_location: Optional[Location] = None
    description: str
    supporting_evidence: str
    suggested_correction: Optional[str] = None
    counterexample_ticket: Optional[Dict[str, Any]] = None


class CoverageReport(BaseModel):
    total_rules: int
    verified_rules: List[str] = Field(default_factory=list)
    unreviewed_rules: List[str] = Field(default_factory=list)
    coverage_percent: float = 100.0
    unsupported_constructs: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    bundle_id: str
    status: VerdictStatus
    summary: str
    findings: List[Finding] = Field(default_factory=list)
    coverage: CoverageReport
    effective_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    check_results: Dict[str, bool] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
