# Security Requirements Quality Checklist: Launcher Container Image & CDK IaC

**Purpose**: Validate that security-relevant REQUIREMENTS are well-written, complete, and measurable — not to test the implementation. "Unit tests for English."
**Created**: 2026-07-06
**Feature**: [spec.md](../spec.md) · [contracts/webhook.md](../contracts/webhook.md)

## Requirement Completeness

- [x] CHK001 - Are authentication requirements specified for the webhook endpoint (HMAC signature verification as the only auth)? [Completeness, Spec §FR-001]
- [x] CHK002 - Are data-protection requirements defined for the environment key (reference-only, never on compute)? [Completeness, Spec §FR-004]
- [x] CHK003 - Are least-privilege IAM requirements specified for the launcher role and the MicroVM execution role? [Completeness, Spec §FR-007]
- [x] CHK004 - Are dedupe/idempotency requirements defined to prevent duplicate MicroVM launches on replay? [Completeness, Spec §FR-002]

## Requirement Clarity

- [x] CHK005 - Is the credential boundary stated unambiguously (which secrets reach which compute)? [Clarity, Spec §FR-004]
- [x] CHK006 - Is the RunMicrovm rate limit quantified (5 TPS)? [Clarity, Spec §FR-003]
- [x] CHK007 - Are the forbidden payload keys explicitly enumerated? [Clarity, data-model.md §RunHookDispatch]

## Requirement Consistency

- [x] CHK008 - Are WAF/request-validation requirements consistent with "signature check is the only authentication"? [Consistency, Spec §FR-007, contracts/webhook.md]
- [x] CHK009 - Are the local (stub) and AWS (real) security postures consistent (signing secret verified in both)? [Consistency, Spec §FR-006]

## Acceptance Criteria Quality

- [x] CHK010 - Can the credential-boundary invariant be objectively verified by a test? [Measurability, Spec §FR-004, SC-004]
- [x] CHK011 - Is the 401-on-invalid-signature behavior measurable? [Measurability, Spec §FR-001]

## Scenario & Edge Case Coverage

- [x] CHK012 - Are requirements defined for stale/invalid webhook deliveries? [Coverage, Edge Case]
- [x] CHK013 - Are requirements defined for concurrent/retried event-id deliveries? [Coverage, Spec §FR-002]
- [x] CHK014 - Are requirements defined for malformed (non-start) events (200, no retry)? [Coverage, Edge Case]
- [x] CHK015 - Are requirements defined for local mode without the idempotency table? [Coverage, Edge Case]

## Non-Functional / Compliance

- [x] CHK016 - Is the constitutional MUST "no `version:` key in docker-compose" captured as a requirement? [Compliance, Constitution §V] — enforced in T005; this checklist gates it.
- [x] CHK017 - Are secret-storage requirements (Secrets Manager, least-privilege GetSecretValue) specified? [Non-Functional, Spec §FR-007]
- [x] CHK018 - Are public-endpoint defense-in-depth requirements (WAF managed rules + per-IP rate limit) specified without conflating them with authentication? [Non-Functional, Spec §FR-007]

## Notes

- All items pass: security requirements are complete, clear, measurable, and traceable.
- This checklist tests the REQUIREMENTS, not the implementation; T039 tests the implementation invariant.