"""
PR diff → risk assessment grounded in past incident memory.
Retrieves semantically similar past incidents, then asks Claude
to identify specific risk patterns in the diff.
"""

import json
import os
import re
import anthropic
from agent.parser import MemoryChunk
from agent.memory import query

_client = None


def _demo_mode() -> bool:
    return os.environ.get("PMA_DEMO_MODE") == "1" or not os.environ.get("ANTHROPIC_API_KEY")


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)


def _format_memory_context(chunks: list[MemoryChunk]) -> str:
    if not chunks:
        return "No relevant past incidents found in memory."
    lines = ["Past incidents that may be relevant:\n"]
    for i, c in enumerate(chunks, 1):
        lines.append(
            f"{i}. [{c.severity}] {c.component} ({c.date})\n"
            f"   Root cause: {c.root_cause}\n"
            f"   Fix pattern: {c.fix_pattern}\n"
            f"   Detection: {c.detection_signal}"
        )
    return "\n".join(lines)


def review_pr(diff: str) -> dict:
    """
    Returns:
    {
        "risk_score": int (0-10),
        "matched_incidents": [MemoryChunk, ...],
        "warnings": [str, ...],
        "recommendation": str,
    }
    """
    matched = query(diff, top_k=3)

    if _demo_mode():
        lower = diff.lower()
        warnings = []
        score = 1
        recommendation = "No incident-shaped risk pattern was detected in this diff."

        if "product.find" in lower or "eager_load" in lower or "with_products" in lower or "joins(:order_items)" in lower:
            score = 9
            warnings.extend([
                "The diff removes eager product loading from the order path.",
                "The serializer now performs Product.find inside an order_items loop, which can recreate an N+1 checkout query pattern.",
                "Checkout no longer uses Order.with_products, so the previous incident guardrail is bypassed.",
            ])
            recommendation = (
                "Block this change until product loading is batched and a query-count regression test proves checkout "
                "stays within the expected query budget."
            )
        elif any(token in lower for token in ["pool:", "connection", "database.yml"]):
            score = 5
            warnings.append("The diff changes database capacity settings; validate this against connection pool history.")
            recommendation = "Require explicit database owner review before merging."

        return {
            "risk_score": score,
            "matched_incidents": matched,
            "warnings": warnings,
            "recommendation": recommendation,
        }

    context = _format_memory_context(matched)

    system = """You are a senior engineer reviewing a PR diff for risk patterns based on past incidents.
Return ONLY a JSON object with these fields:
{
  "risk_score": <integer 0-10, where 0=no risk, 10=certain incident>,
  "warnings": ["specific warning string", ...],
  "recommendation": "one paragraph explaining the risk and what the author should check or change"
}
Be specific — reference exact line patterns in the diff when warning about risks."""

    prompt = f"""{context}

PR Diff to review:
```diff
{diff}
```

Based on the past incidents above, analyze this diff for risk patterns that could cause a similar incident.
Return your assessment as JSON."""

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(_strip_json_fences(response.content[0].text))
    return {
        "risk_score": int(data.get("risk_score", 0)),
        "matched_incidents": matched,
        "warnings": data.get("warnings", []),
        "recommendation": data.get("recommendation", ""),
    }
