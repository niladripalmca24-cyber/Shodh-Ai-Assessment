"""
Independent Ground-Truth Routing Oracle.
Never imports or shares code with the Z3 verifier.
Used to establish indisputable reference routes for evaluation bundles and counterexamples.
"""

from typing import Any, Dict


def evaluate_ticket_oracle(ticket: Dict[str, Any], wait_threshold_seconds: int = 1800, vip_active: bool = False) -> str:
    """
    Independent reference implementation of support ticket routing:
      R0 (optional): VIP customer -> "vip_queue"
      R1: Missing category -> "manual_review"
      R2: Otherwise, urgent -> "priority_queue"
      R3: Otherwise, waiting >= wait_threshold_seconds -> "escalation"
      Default: "normal_queue"
    """
    cat_missing = ticket.get("category_missing", False)
    if ticket.get("category") is None:
        cat_missing = True
    
    urgent = bool(ticket.get("urgent", False))
    wait_time = int(ticket.get("wait_seconds", ticket.get("waiting_time", 0)))
    vip = bool(ticket.get("vip", False))

    if vip_active and vip:
        return "vip_queue"

    if cat_missing:
        return "manual_review"
    elif urgent:
        return "priority_queue"
    elif wait_time >= wait_threshold_seconds:
        return "escalation"
    else:
        return "normal_queue"
