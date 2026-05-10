"""
postmortem text → structured MemoryChunk via Claude extraction.
System prompt is cached (cache_control: ephemeral) for batch ingestion efficiency.
"""

import json
import re
import uuid
import anthropic
from pydantic import BaseModel, Field
from typing import List

_client = anthropic.Anthropic()

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


def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)


def parse_postmortem(text: str) -> MemoryChunk:
    response = _client.messages.create(
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
