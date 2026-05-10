"""
PR diff → risk assessment grounded in past incident memory.
Retrieves semantically similar past incidents, then asks Claude
to identify specific risk patterns in the diff.
"""

import json
import re
import anthropic
from agent.parser import MemoryChunk
from agent.memory import query

_client = anthropic.Anthropic()


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

    response = _client.messages.create(
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
