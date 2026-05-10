# Postmortem: Auth Service — Session Tokens Written to Application Logs — 2025-09-17

**Severity:** SEV-1  
**Duration:** 6 hours (detected via security audit, not real-time alert)  
**Incident Commander:** Priya Nair

## Summary

A debug logging statement introduced in auth-service v2.14.0 serialized the entire request context, including raw JWT session tokens, into structured application logs. Logs were shipped to an externally-accessible S3 bucket used by the analytics team.

## Timeline

- 2025-09-10 — auth-service v2.14.0 deployed with `logger.debug(ctx)` statement
- 2025-09-17 09:00 — Security audit script detects JWT patterns in S3 log bucket
- 09:45 — Incident declared; tokens rotating begins
- 12:00 — All ~480,000 active session tokens rotated and invalidated
- 15:00 — Logging statement removed and hotfix deployed; S3 bucket locked down

## Root Cause

A developer added `logger.debug("incoming request", ctx=request_context)` during a debugging session and forgot to remove it before merging. The `request_context` object included the decoded JWT payload. Log aggregation shipped logs to S3 without field-level redaction.

## Fix

1. Removed the offending `logger.debug` call
2. Added a log scrubbing middleware that redacts fields matching `token`, `jwt`, `authorization`, `secret`, `password`
3. Restricted S3 log bucket to internal VPC access only
4. Rotated all active session tokens

## Prevention

- Added `bandit` static analysis rule to CI blocking any log statement that serializes a full context object
- Implemented field-level PII/secret redaction in the log aggregation pipeline
- Security review required for auth-service PRs

## Impact

- ~480,000 session tokens exposed for 7 days
- Mandatory security disclosure to affected enterprise customers
- No confirmed exploitation detected
