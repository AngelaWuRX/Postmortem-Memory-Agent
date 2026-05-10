"""
Wraps pr_reviewer and applies a threshold-based routing decision.

  0–3   → SAFE          (merge freely)
  4–6   → NEEDS REVIEW  (require explicit approval)
  7–10  → BLOCK         (do not merge, fix first)
"""

from agent.pr_reviewer import review_pr

SAFE_MAX = 3
BLOCK_MIN = 7


def route(diff: str) -> dict:
    """
    Returns review dict augmented with:
      decision: "safe" | "needs-review" | "block"
      decision_label: human-readable string with emoji
    """
    review = review_pr(diff)
    score = review["risk_score"]

    if score <= SAFE_MAX:
        decision = "safe"
        label = "✅ SAFE — clear to merge"
    elif score < BLOCK_MIN:
        decision = "needs-review"
        label = "⚠️ NEEDS REVIEW — get explicit approval"
    else:
        decision = "block"
        label = "🚫 BLOCK — do not merge, address warnings first"

    return {**review, "decision": decision, "decision_label": label}
