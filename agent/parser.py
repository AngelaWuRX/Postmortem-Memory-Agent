"""
postmortem text → structured MemoryChunk via Claude extraction.
System prompt is cached (cache_control: ephemeral) for batch ingestion efficiency.
"""

import json
import os
import re
import uuid
import anthropic
from pydantic import BaseModel, Field
from typing import List

_client = None

_SYSTEM_PROMPT = """You are a postmortem analyst. Extract structured information from the given postmortem document and return ONLY a valid JSON object with these exact fields:
{
  "component": "the service or component that failed",
  "root_cause": "concise root cause (1-2 sentences)",
  "fix_pattern": "what was done to fix it (1-2 sentences)",
  "detection_signal": "what metric/alert/signal detected the issue",
  "severity": "SEV-1, SEV-2, SEV-3, or SEV-4",
  "date": "incident date as YYYY-MM-DD",
  "tags": ["list", "of", "relevant", "tags"],
  "raw_summary": "one sentence summarizing the incident for semantic search"
}
Return only the JSON object, no markdown, no explanation."""


class MemoryChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component: str
    root_cause: str
    fix_pattern: str
    detection_signal: str
    severity: str
    date: str
    tags: List[str]
    raw_summary: str

    def to_chroma_metadata(self) -> dict:
        return {
            "component": self.component,
            "root_cause": self.root_cause,
            "fix_pattern": self.fix_pattern,
            "detection_signal": self.detection_signal,
            "severity": self.severity,
            "date": self.date,
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_chroma(cls, id: str, metadata: dict, document: str) -> "MemoryChunk":
        return cls(
            id=id,
            component=metadata["component"],
            root_cause=metadata["root_cause"],
            fix_pattern=metadata["fix_pattern"],
            detection_signal=metadata["detection_signal"],
            severity=metadata["severity"],
            date=metadata["date"],
            tags=json.loads(metadata.get("tags", "[]")),
            raw_summary=document,
        )


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


def _extract_demo_chunk(text: str) -> MemoryChunk:
    lower = text.lower()
    title_match = re.search(r"^#\s*(?:postmortem:\s*)?(.+?)(?:\s+[—-]\s+\d{4}-\d{2}-\d{2})?$", text, re.MULTILINE)
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    severity_match = re.search(r"\bSEV-[1-4]\b", text)

    if "n+1" in lower or "eager" in lower:
        component = "payments-service"
        root_cause = "An ORM migration removed eager loading, causing checkout serialization to lazy-load products one item at a time."
        fix_pattern = "Restore eager loading, batch product lookups, add query-count regression coverage, and keep supporting indexes in place."
        detection_signal = "payments.checkout.p99 latency above 2s with elevated DB CPU and repeated product queries."
        tags = ["payments", "database", "orm", "n-plus-one", "latency"]
    elif "token" in lower or "jwt" in lower:
        component = "auth-service"
        root_cause = "Sensitive authentication tokens were emitted into debug logs and exported to shared object storage."
        fix_pattern = "Redact secrets at log boundaries, disable debug logging in production, and rotate exposed credentials."
        detection_signal = "Security scan detected JWT-shaped values in production log exports."
        tags = ["auth", "security", "logging", "token-leak"]
    elif "connection pool" in lower or "missing index" in lower:
        component = "database"
        root_cause = "A slow unindexed query exhausted the application database connection pool under load."
        fix_pattern = "Add the missing index, cap expensive query fanout, and alert on pool saturation before request failures."
        detection_signal = "Connection pool utilization and query latency alerts crossed production thresholds."
        tags = ["database", "index", "connection-pool", "latency"]
    elif "cache stampede" in lower or "thundering herd" in lower:
        component = "cache layer"
        root_cause = "Coordinated cache expiry caused many workers to recompute the same expensive value at once."
        fix_pattern = "Add request coalescing, jitter cache TTLs, and protect recomputation with a lock."
        detection_signal = "Cache miss rate and upstream CPU spiked during rollout."
        tags = ["cache", "stampede", "rollout", "availability"]
    elif "oom" in lower or "memory" in lower:
        component = "worker"
        root_cause = "A background export job accumulated unbounded data in memory until workers were killed."
        fix_pattern = "Stream data in bounded batches and add memory limits plus regression coverage for large exports."
        detection_signal = "Worker OOM kill alerts and stalled export queues."
        tags = ["worker", "oom", "memory", "batching"]
    else:
        component = title_match.group(1).strip() if title_match else "unknown-service"
        root_cause = "The incident report describes a production failure mode that should be retained for future risk checks."
        fix_pattern = "Capture the mitigation pattern, add prevention coverage, and monitor for the same signal."
        detection_signal = "Incident report alerts and operational signals."
        tags = ["incident", "postmortem", "demo"]

    return MemoryChunk(
        component=component,
        root_cause=root_cause,
        fix_pattern=fix_pattern,
        detection_signal=detection_signal,
        severity=severity_match.group(0) if severity_match else "SEV-3",
        date=date_match.group(1) if date_match else "2026-01-01",
        tags=tags,
        raw_summary=f"{component}: {root_cause} Fix: {fix_pattern}",
    )


def parse_postmortem(text: str) -> MemoryChunk:
    if _demo_mode():
        return _extract_demo_chunk(text)

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": text}],
    )
    data = json.loads(_strip_json_fences(response.content[0].text))
    return MemoryChunk(**data)
