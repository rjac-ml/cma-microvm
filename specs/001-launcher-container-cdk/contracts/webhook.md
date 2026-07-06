# Contract: POST /webhook

Phase 1 output. The launcher exposes exactly one HTTP contract: the Anthropic
webhook endpoint behind API Gateway. This documents the wire contract; see
[data-model.md](../data-model.md) for the parsed entities.

## Endpoint

`POST /webhook` — Anthropic delivers `session.status_run_started` here. In prod
this is fronted by API Gateway REST (request validation + WAFv2 WebACL); the
launcher performs **in-process HMAC signature verification** as the only
authentication. Locally (uvicorn in compose) the same route is exposed directly
with the stub MicroVM client.

## Request

- **Content-Type**: `application/json`
- **Headers**: Anthropic webhook signature headers (verified by
  `anthropic` SDK `client.beta.webhooks.unwrap(body, headers, signing_secret)`).
- **Body**: the Anthropic webhook event envelope:

```json
{
  "type": "session.status_run_started",
  "id": "evt_...",
  "created_at": "ISO8601",
  "data": { "type": "session", "id": "sesn_..." }
}
```

API Gateway request validation enforces the envelope structure (not `data.type`
values); the launcher verifies the HMAC over the **raw** body.

## Responses

| Status | Condition | Body |
|--------|-----------|------|
| 401 | Signature verification fails (invalid or stale) | `signature verification failed` |
| 200 | Valid signature, non-start event type | `ignored` |
| 200 | Valid signature, missing `event_id` or `session_id` (malformed) | `ignored` (200, not 4xx — Anthropic must not retry malformed events) |
| 200 | Event id already in progress / already handled (idempotency) | `in progress` or `{ "microvm_id": ..., "session_id": ... }` |
| 200 | Launch succeeded | `{ "microvm_id": "<id>", "session_id": "<id>" }` (stub `microvm_id` locally) |
| 502 | `RunMicrovm` failed | `{ "error": "run_microvm_failed", "session_id": "<id>" }` (non-2xx → Anthropic retries) |

## Non-secret guarantee

The handler reads only the **signing secret** (to verify). The dispatch it
builds contains a **reference** to the environment-key secret (`ENVIRONMENT_KEY_
SECRET_ID`), never the key. `ANTHROPIC_API_KEY` and `ANTHROPIC_ENVIRONMENT_KEY`
are forbidden in the run-hook payload (enforced by `shared/payload.py`).