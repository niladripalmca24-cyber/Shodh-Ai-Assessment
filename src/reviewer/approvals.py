from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional, Tuple
from reviewer.schemas import ApprovalRecord, ApprovalStatus, Finding, Location, Severity, SourceRequirement


class ContradictoryApprovalError(Exception):
    pass


def resolve_effective_requirements(
    source_requirements: List[SourceRequirement],
    approval_records: List[ApprovalRecord],
) -> Tuple[List[SourceRequirement], List[Finding], bool]:
    """
    Applies top-level approved changes to source requirements.
    Enforces trust boundaries:
      1. Only top-level ApprovalRecord with status == 'APPROVED' are applied.
      2. Claims inside prose or code comments are ignored.
      3. Contradictory approval detection: if two APPROVED records modify the same rule attribute
         to conflicting values, emit CONTRADICTORY_APPROVAL finding and signal has_conflict=True.
      4. Sorts approved changes deterministically by (revision, sequence_order).
    """
    findings: List[Finding] = []
    has_conflict = False

    # Clone source requirements by ID
    req_map: Dict[str, SourceRequirement] = {
        req.id: copy.deepcopy(req) for req in source_requirements
    }

    # Filter for APPROVED records
    approved_records = [rec for rec in approval_records if rec.status == ApprovalStatus.APPROVED]

    # Check for contradictions among approved records:
    # A contradiction occurs if multiple APPROVED records target the same (target_rule_id, attribute)
    # with different new_values at the same revision, or without clear ordering.
    seen_modifications: Dict[Tuple[str, str], List[ApprovalRecord]] = {}
    for rec in approved_records:
        key = (rec.target_rule_id, rec.attribute)
        seen_modifications.setdefault(key, []).append(rec)

    for (rule_id, attr), recs in seen_modifications.items():
        if len(recs) > 1:
            # Check if all new_values are identical or if they conflict
            unique_values = {str(r.new_value) for r in recs}
            if len(unique_values) > 1:
                # Contradictory approval detected!
                has_conflict = True
                conflict_details = ", ".join(
                    f"Rec({r.id}: val={r.new_value}, rev={r.revision})" for r in recs
                )
                findings.append(
                    Finding(
                        id="CONTRADICTORY_APPROVAL",
                        severity=Severity.WARNING,
                        rule_ref=rule_id,
                        artifact_location=recs[0].location,
                        description=(
                            f"Contradictory approval records detected for rule '{rule_id}' attribute '{attr}'. "
                            f"Multiple approved records specify conflicting target values: [{conflict_details}]."
                        ),
                        supporting_evidence=(
                            f"Found {len(recs)} conflicting approved records for rule {rule_id}. "
                            "Approval resolver refuses to silently choose a convenient version."
                        ),
                        suggested_correction="Revoke one of the conflicting approval records or issue an explicit superseding revision.",
                    )
                )

    if has_conflict:
        return list(req_map.values()), findings, True

    # Sort approved records by revision asc, sequence_order asc
    sorted_approved = sorted(approved_records, key=lambda r: (r.revision, r.sequence_order))

    # Apply approved updates
    for rec in sorted_approved:
        if rec.target_rule_id not in req_map:
            findings.append(
                Finding(
                    id="ORPHAN_APPROVAL_RECORD",
                    severity=Severity.WARNING,
                    rule_ref=rec.target_rule_id,
                    artifact_location=rec.location,
                    description=f"Approval record '{rec.id}' targets non-existent rule '{rec.target_rule_id}'",
                    supporting_evidence=f"Target rule {rec.target_rule_id} is missing from source requirements.",
                )
            )
            continue

        target = req_map[rec.target_rule_id]
        if rec.attribute in ("condition_dsl", "condition"):
            target.condition_dsl = str(rec.new_value)
        elif rec.attribute in ("target_queue", "queue"):
            target.target_queue = str(rec.new_value)
        elif rec.attribute in ("order", "precedence"):
            target.order = int(rec.new_value)
        elif rec.attribute == "threshold":
            # Replace threshold in condition_dsl
            # e.g., replacing 30 minutes with 25 minutes
            old_val_str = str(rec.old_value)
            new_val_str = str(rec.new_value)
            target.condition_dsl = target.condition_dsl.replace(old_val_str, new_val_str)
        target.version = f"{target.version}.rev{rec.revision}"

    effective_list = sorted(req_map.values(), key=lambda r: r.order)
    return effective_list, findings, False
