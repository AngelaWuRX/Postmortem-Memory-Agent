"""
MemoryChunk → four concrete artifacts saved to generated/:
  regression_test.py  — pytest that would have caught the bug
  monitor.yaml        — Prometheus/Datadog alert rule
  runbook.md          — step-by-step incident response guide
  ticket.md           — prevention work ticket (Jira/Linear style)
"""

import re
import os
import anthropic
from pathlib import Path
from agent.parser import MemoryChunk

_client = None
GENERATED_DIR = Path("generated")


def _demo_mode() -> bool:
    return os.environ.get("PMA_DEMO_MODE") == "1" or not os.environ.get("ANTHROPIC_API_KEY")


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _call(prompt: str, system: str, max_tokens: int = 1024) -> str:
    response = _get_client().messages.create(
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
    if _demo_mode():
        return f'''"""Regression coverage for the {chunk.component} incident."""

from unittest.mock import Mock


def test_checkout_product_loading_stays_batched():
    """Catches N+1 style regressions by enforcing a small query budget."""
    query_counter = Mock()

    def load_order_with_products(order_id):
        query_counter("orders")
        query_counter("order_items")
        query_counter("products")
        return {{"id": order_id, "products": ["sku-1", "sku-2"]}}

    order = load_order_with_products("ord_123")

    assert order["products"]
    assert query_counter.call_count <= 3
'''

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
    if _demo_mode():
        return f"""apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: {chunk.component.replace("_", "-")}-incident-guardrails
spec:
  groups:
    - name: {chunk.component}.risk
      rules:
        - alert: CheckoutLatencyCritical
          expr: histogram_quantile(0.99, rate(payments_checkout_duration_seconds_bucket[5m])) > 2
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Checkout p99 latency is above incident threshold"
            description: "{chunk.detection_signal}"
            runbook_url: "https://runbooks.example.com/{chunk.component}"
        - alert: CheckoutLatencyWarning
          expr: histogram_quantile(0.99, rate(payments_checkout_duration_seconds_bucket[5m])) > 1
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Checkout p99 latency is elevated"
            description: "Early warning for recurring {chunk.component} incident pattern."
            runbook_url: "https://runbooks.example.com/{chunk.component}"
"""

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
    if _demo_mode():
        return f"""# Runbook: {chunk.component} Recurrence

## Alert
{chunk.detection_signal}

## Impact
Users may see elevated latency, failed requests, or degraded checkout completion.

## Diagnosis steps
1. Check p99 latency and error rate.
   ```bash
   kubectl top pods -n production
   ```
2. Inspect recent database query volume.
   ```sql
   SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY calls DESC LIMIT 10;
   ```
3. Compare the active deploy against the last known safe revision.

## Fix
1. Revert or patch the risky change.
2. Restore the prevention pattern: {chunk.fix_pattern}
3. Deploy and watch latency plus database CPU.

## Verification
Confirm p99 latency, error rate, and saturation metrics return to baseline for 15 minutes.

## Escalation
Page the service owner and database on-call if the issue remains above threshold after rollback.
"""

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
    if _demo_mode():
        return f"""# [TICKET] Prevent recurrence: {chunk.component}
**Priority:** P1
**Component:** {chunk.component}
**Labels:** {", ".join(chunk.tags)}

## Problem
{chunk.root_cause}

## Root cause reference
Incident date: {chunk.date}  
Severity: {chunk.severity}

## Acceptance criteria
- [ ] Add regression coverage for the failure mode.
- [ ] Add or tune monitoring for: {chunk.detection_signal}
- [ ] Document the response path in the service runbook.
- [ ] Validate the fix in staging before release.

## Implementation notes
{chunk.fix_pattern}

## Definition of done
The recurring risk is covered by CI, monitored in production, and documented for on-call response.
"""

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
