# Postmortem Memory Agent

> A semantic memory layer for incident response agents — compresses past postmortems into token-tiny chunks, generates actionable artifacts, and blocks risky PRs before they ship.

## Two surfaces, two audiences

| | Engineers | Managers |
|---|---|---|
| **Interface** | `pma` CLI | Streamlit web app |
| **Install** | `pip install git+https://github.com/AngelaWuRX/Postmortem-Memory-Agent` | `streamlit run app.py` |
| **Use case** | Ingest from terminal, pipe into CI, review diffs | Browse history, assess PRs, download artifacts |

Built as a complementary add-on to [Entelligence.AI's Ellie](https://entelligence.ai). Ellie reads diffs and postmortems and links alerts to code history. The gap: every incident starts cold. This agent solves the memory problem — and closes the loop by generating the artifacts that prevent recurrence.

---

## The Problem

When a new incident fires, your AI agent has no memory of past postmortems. It either:
- **Burns massive tokens** re-reading full docs (~2,000 tokens each) to build context, or
- **Starts cold** with zero history, giving generic advice instead of specific fixes

And when the incident is over, someone has to manually write the regression test, monitoring rule, runbook, and prevention ticket. Nobody does.

---

## What This Builds

```
Postmortem doc
      │
      ▼
  [parser.py] ──── Claude extracts structured chunk (~150 tokens vs 2,000)
      │
      ├──▶ [memory.py] ──── ChromaDB stores + indexes for semantic search
      │
      └──▶ [artifact_generator.py] ──── Claude generates:
                │                          regression_test.py
                │                          monitor.yaml
                │                          runbook.md
                │                          ticket.md
                │
New PR diff ──▶ [pr_reviewer.py] ──── retrieves relevant past incidents
                │                      analyzes diff for matching risk patterns
                ▼
           [router.py] ──── ✅ SAFE  /  ⚠️ NEEDS REVIEW  /  🚫 BLOCK
```

---

## Quick Start

### Engineers — CLI

```bash
# Install directly from GitHub
pip install git+https://github.com/AngelaWuRX/Postmortem-Memory-Agent.git

export ANTHROPIC_API_KEY=sk-ant-...

# Ingest a postmortem (parses + stores + generates all artifacts)
pma ingest postmortem.md

# Ingest a whole folder at once
pma ingest sample_data/

# Review a PR diff for incident risk
pma review my_branch.diff

# Query memory with an alert
pma query "payments p99 spiking, DB CPU at 90%"

# List all stored incidents
pma memory
```

### Managers — Web App

```bash
git clone https://github.com/AngelaWuRX/Postmortem-Memory-Agent
cd Postmortem-Memory-Agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```
---

## App Tabs

### 📥 Ingest Postmortem
Paste a postmortem → Claude extracts a structured 150-token memory chunk and generates four artifacts instantly. Load any of the six sample postmortems to see it in action.

### 🔍 Review PR
Paste a PR diff → the agent retrieves semantically similar past incidents and returns a **SAFE / NEEDS REVIEW / BLOCK** decision with specific line-level warnings. Load `future_pr_bad.diff` (removes ORM eager loading) vs `future_pr_safe.diff` (CSS change) to see the contrast.

### 🗃️ Memory Browser
Browse all stored incidents in a table. Download `incident_memory.json`. See the token compression ratio live.

---

## Architecture

| File | Purpose |
|---|---|
| `agent/parser.py` | Postmortem text → `MemoryChunk` via Claude (with prompt caching) |
| `agent/memory.py` | ChromaDB persistent vector store + JSON sidecar |
| `agent/artifact_generator.py` | `MemoryChunk` → regression test, monitor YAML, runbook, ticket |
| `agent/pr_reviewer.py` | PR diff + memory → risk score, warnings, recommendation |
| `agent/router.py` | Threshold-based SAFE / NEEDS REVIEW / BLOCK decision |
| `app.py` | Streamlit UI (3 tabs) |
| `sample_data/` | 6 postmortems + risky/safe PR diffs |
| `generated/` | Pre-generated artifacts from the payments N+1 incident |

---

## Token Efficiency

| Approach | Tokens per incident | For 3 incidents |
|---|---|---|
| Load full postmortem docs | ~2,000 | ~6,000 |
| Load memory chunks | ~150 | ~450 |
| **Savings** | **13×** | **~5,550 tokens saved** |

Prompt caching (`cache_control: ephemeral`) on the stable extraction system prompt further reduces cost during batch ingestion.

---

## Sample Data

Six realistic postmortems across failure modes:

| File | Pattern |
|---|---|
| `postmortem_payments_n_plus_one.md` | N+1 ORM query → checkout latency |
| `postmortem_auth_token_leak.md` | Debug log leaking JWTs to S3 |
| `postmortem_db_connection_pool.md` | Missing index → connection exhaustion |
| `postmortem_cache_stampede.md` | Thundering herd on rolling deploy |
| `postmortem_oom_worker.md` | Unbounded memory in export worker |
| `postmortem_search_index_drift.md` | Silent Kafka consumer crash |

Two sample PR diffs:
- `future_pr_bad.diff` — removes `eager_load(:products)` (should trigger **BLOCK**)
- `future_pr_safe.diff` — CSS/copy changes (should pass **SAFE**)

---

## Pre-Generated Artifacts

The `generated/` folder contains example output from ingesting the payments N+1 postmortem:

- **`regression_test.py`** — pytest that asserts checkout issues ≤ 3 DB queries
- **`monitor.yaml`** — PrometheusRule with warning + critical alerts tuned to the exact failure thresholds
- **`runbook.md`** — step-by-step response with exact kubectl/SQL commands
- **`ticket.md`** — P1 prevention ticket with acceptance criteria and Bullet gem setup
- **`incident_memory.json`** — human-readable memory store audit trail
