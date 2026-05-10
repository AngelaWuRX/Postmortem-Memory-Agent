# Postmortem: Report Worker — OOM Kills During Large Export Jobs — 2025-07-14

**Severity:** SEV-2  
**Duration:** Recurring over 3 days; fully resolved 2025-07-16  
**Incident Commander:** Daniel Kim

## Summary

The report-worker service began OOM-crashing when processing large enterprise export jobs (>500,000 rows). A memory leak in the CSV serializer accumulated unbounded memory because rows were collected into a list before streaming, rather than being streamed row-by-row to the response.

## Timeline

- 2025-07-12 — First OOM kill reported; pod restarts masked issue (report retried successfully with smaller dataset)
- 2025-07-14 — Three enterprise customers report failed exports; OOM kills confirmed in logs
- 14:30 — Memory profiling with `memory_profiler` identifies CSV buffer accumulation
- 2025-07-15 — PR #6204: switched CSV serializer to chunked streaming (yield rows, 1000 at a time)
- 2025-07-16 — Deployed; 500K-row export now peaks at 180MB vs prior 4.2GB

## Root Cause

The CSV export function called `list(queryset)` to materialize the entire queryset before serialization. For large enterprise exports, this loaded all rows into memory simultaneously. With multiple concurrent export jobs, memory usage compounded until the 2GB pod limit was exceeded.

## Fix

1. Replaced `list(queryset)` with chunked iteration using `queryset.iterator(chunk_size=1000)`
2. Switched response type to `StreamingHttpResponse` to avoid buffering the full CSV in memory
3. Added per-job memory limit guard: jobs over 1M rows are split into paginated exports

## Prevention

- Load test for export jobs added to CI: must complete a 500K-row export under 512MB memory
- Kubernetes `resources.limits.memory` reduced to 1GB (forced earlier detection)

## Impact

- 3 enterprise customers affected with failed exports over 3 days
- Manual re-exports performed by support team; no data loss
