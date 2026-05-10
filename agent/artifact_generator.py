"""
MemoryChunk → four concrete artifacts saved to generated/:
  regression_test.py  — pytest that would have caught the bug
  monitor.yaml        — Prometheus/Datadog alert rule
  runbook.md          — step-by-step incident response guide
  ticket.md           — prevention work ticket (Jira/Linear style)
"""

import re
import anthropic
from pathlib import Path
from agent.parser import MemoryChunk

_client = anthropic.Anthropic()
GENERATED_DIR = Path("generated")


def _call(prompt: str, system: str, max_tokens: int = 1024) -> str:
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _strip_fences(text: str, lang: str = "") -> str:
    text = re.sub(rf"^```{lang}\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)


def generate_regression_test(chunk: MemoryChunk) -> str:
    system = "You are a senior software engineer writing pytest regression tests. Output only valid Python code, no explanation."
    prompt = f"""Write a pytest regression test for this incident:

Component: {chunk.component}
Root cause: {chunk.root_cause}
Fix pattern: {chunk.fix_pattern}
Detection signal: {chunk.detection_signal}
Tags: {', '.join(chunk.tags)}

The test should:
1. Reproduce (or assert against) the failure mode described in the root cause
2. Verify the fix pattern is in place
3. Include clear docstrings explaining what each test catches
4. Use realistic mock data and assertions
5. Be immediately runnable with standard pytest + unittest.mock

Output only the Python file content."""
    return _strip_fences(_call(prompt, system, max_tokens=1500), "python")


def generate_monitor(chunk: MemoryChunk) -> str:
    system = "You are a site reliability engineer. Output only valid YAML, no explanation."
    prompt = f"""Write a Prometheus alerting rule (YAML) for this incident pattern:

Component: {chunk.component}
Detection signal: {chunk.detection_signal}
Severity: {chunk.severity}
Root cause: {chunk.root_cause}
Tags: {', '.join(chunk.tags)}

Include:
- A PrometheusRule with groups and rules
- Alert name, expr, for, labels (severity), and annotations (summary, description, runbook_url)
- Realistic metric names and thresholds based on the detection signal
- A second warning-level alert that fires earlier as a precursor

Output only the YAML."""
    return _strip_fences(_call(prompt, system, max_tokens=1024), "yaml")


def generate_runbook(chunk: MemoryChunk) -> str:
    system = "You are an SRE writing an incident runbook. Output markdown."
    prompt = f"""Write a concise incident response runbook for:

Component: {chunk.component}
Severity: {chunk.severity}
Detection signal: {chunk.detection_signal}
Root cause: {chunk.root_cause}
Known fix: {chunk.fix_pattern}
Tags: {', '.join(chunk.tags)}

Structure:
# Runbook: [incident title]
## Alert
## Impact
## Diagnosis steps (numbered, with exact commands)
## Fix (numbered steps with code blocks)
## Verification
## Escalation

Be specific — include realistic kubectl, SQL, or CLI commands."""
    return _call(prompt, system, max_tokens=1500)


def generate_ticket(chunk: MemoryChunk) -> str:
    system = "You are an engineering manager writing a prevention ticket. Output markdown."
    prompt = f"""Write a Jira/Linear prevention ticket for:

Component: {chunk.component}
Incident date: {chunk.date}
Severity: {chunk.severity}
Root cause: {chunk.root_cause}
Fix applied: {chunk.fix_pattern}
Tags: {', '.join(chunk.tags)}

Structure:
# [TICKET] Prevent recurrence: [short title]
**Priority:** ...
**Component:** ...
**Labels:** ...

## Problem
## Root cause reference
## Acceptance criteria (checkbox list)
## Implementation notes
## Definition of done"""
    return _call(prompt, system, max_tokens=1024)


def generate_all(chunk: MemoryChunk) -> dict[str, str]:
    """Generate all four artifacts. Returns {filename: content}."""
    return {
        "regression_test.py": generate_regression_test(chunk),
        "monitor.yaml": generate_monitor(chunk),
        "runbook.md": generate_runbook(chunk),
        "ticket.md": generate_ticket(chunk),
    }


def save_artifacts(chunk: MemoryChunk, artifacts: dict[str, str]) -> dict[str, Path]:
    GENERATED_DIR.mkdir(exist_ok=True)
    saved = {}
    for filename, content in artifacts.items():
        path = GENERATED_DIR / filename
        path.write_text(content)
        saved[filename] = path
    return saved
