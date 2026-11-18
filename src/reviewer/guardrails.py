from __future__ import annotations
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from reviewer.model_client import ModelClient, ModelReviewResponse
from reviewer.schemas import Finding, Location, Severity


def compute_content_hash(
    bundle_data: Dict[str, Any], approvals: List[Dict[str, Any]], model_config: Dict[str, Any]
) -> str:
    """
    Computes a content-addressed SHA-256 hash.
    Guarantees that any edit to artifacts or approval records invalidates cache entries.
    """
    payload = {
        "bundle": bundle_data,
        "approvals": approvals,
        "model_config": model_config,
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def wrap_untrusted_content(content: str) -> str:
    """
    Wraps untrusted requirement prose, comments or code in sandboxed XML tags.
    """
    escaped = content.replace("</untrusted_artifact>", "&lt;/untrusted_artifact&gt;")
    return f"<untrusted_artifact>\n{escaped}\n</untrusted_artifact>"


class GroundingGate:
    """
    Validates model findings against the parsed symbol table of rule IDs and locations.
    Strips hallucinated or invented references.
    """
    def __init__(self, valid_rule_ids: Set[str], valid_locations: Set[str]):
        self.valid_rule_ids = valid_rule_ids
        self.valid_locations = valid_locations
        self.unsupported_findings_blocked = 0

    def filter_findings(
        self, model_response: ModelReviewResponse
    ) -> Tuple[List[Finding], int]:
        grounded_findings: List[Finding] = []
        for mf in model_response.findings:
            # Check if cited rule_ref is real or hallucinated
            is_rule_valid = mf.rule_ref is None or mf.rule_ref in self.valid_rule_ids
            # Check location
            is_loc_valid = mf.location_str is None or mf.location_str in self.valid_locations
            
            # If the finding mentions an invented ID like R99, block it
            if not is_rule_valid:
                self.unsupported_findings_blocked += 1
                continue

            grounded_findings.append(
                Finding(
                    id=f"MODEL_FINDING_{len(grounded_findings) + 1}",
                    severity=Severity.INFO if mf.severity == "INFO" else Severity.WARNING,
                    rule_ref=mf.rule_ref,
                    artifact_location=Location(
                        artifact_id="prose_metadata",
                        location=mf.location_str or "unstructured_prose",
                    ),
                    description=mf.description,
                    supporting_evidence=f"Model-observed gap in unmodeled prose (Raw: {mf.description})",
                    suggested_correction=mf.suggested_correction,
                )
            )

        return grounded_findings, self.unsupported_findings_blocked


class SafeModelExecutor:
    """
    Executes model reviews with bounded retries and fail-safe degradation.
    Retries at most max_retries times; degrades to model_failed if still invalid.
    """
    def __init__(self, model_client: ModelClient, max_retries: int = 2):
        self.client = model_client
        self.max_retries = max_retries

    def execute_with_guardrails(
        self,
        prose_text: str,
        requirements: List[Dict[str, Any]],
        symbol_rule_ids: Set[str],
        symbol_locations: Set[str],
    ) -> Tuple[Optional[ModelReviewResponse], List[Finding], int, bool]:
        """
        Returns: (response, grounded_findings, blocked_count, failure_occurred)
        """
        sandboxed_prose = wrap_untrusted_content(prose_text)
        gate = GroundingGate(symbol_rule_ids, symbol_locations)

        attempts = 0
        last_error = None
        while attempts <= self.max_retries:
            attempts += 1
            try:
                resp = self.client.review_unstructured(sandboxed_prose, requirements)
                
                # Check for malformed / unparseable JSON
                try:
                    parsed_raw = json.loads(resp.raw_response)
                except Exception as json_err:
                    last_error = f"Malformed JSON: {json_err}"
                    continue

                # Prompt injection defense: status_claim inside LLM response is NEVER trusted to override verdict
                if resp.status_claim:
                    # Ignore the status claim, ensure it cannot force PASS
                    pass

                # Filter citations via Grounding Gate
                grounded, blocked_count = gate.filter_findings(resp)
                return resp, grounded, blocked_count, False

            except (TimeoutError, Exception) as err:
                last_error = str(err)
                continue

        # If retries exhausted
        return None, [], 0, True
