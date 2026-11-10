# API

Frontend writes the contract while building screens, Backend implements it. `contracts/openapi.yaml` is the only description of the API; the client, Zod schemas and mocks are generated from it.

## Conventions

| Topic | Rule | Example |
| --- | --- | --- |
| Base path | Versioned | `/api/v1/...` |
| Naming | Plural nouns, kebab-case paths, camelCase JSON | `GET /api/v1/resource-types`, `resourceTypeId` |
| IDs | UUIDv7 strings | `0193f4c2-...` |
| Time | ISO 8601 with offset; stored in UTC; sites return their timezone | `2026-12-15T14:00:00+07:00` |
| Lists | Cursor pagination | `?limit=50&cursor=...` → `data`, `nextCursor` |
| Lifecycle moves | Action endpoints; `status` is never writable | `POST /bookings/{id}/check-in`, `/cancel`, `/approve` |
| Auth | `Authorization: Bearer <JWT>` | — |
| Tenant | `X-Tenant-Id` header, checked against the user's memberships on every request; never from URL or body | — |
| Retries | `Idempotency-Key` header when creating bookings | — |
| Config edits | Carry `baseVersion`; stale → `STALE_VERSION` | — |
| Breaking changes | Additive changes are free; removals and renames need a new version | — |

Spectral checks these rules on every merge request.

## Errors

Every error uses problem details (RFC 9457) with a stable `code`. The frontend handles errors by `code`, never by message. Example: [examples/error-booking-denied.json](examples/error-booking-denied.json).

| Code | Status | When |
| --- | --- | --- |
| `VALIDATION_FAILED` | 422 | Bad input; per-field `errors` |
| `BOOKING_DENIED` | 422 | A rule blocked it; `reasons` from the rule trace |
| `SLOT_TAKEN` | 409 | Someone else holds the slot |
| `INVALID_TRANSITION` | 409 | A move the lifecycle doesn't allow |
| `STALE_VERSION` | 409 | Config edit based on an old version |
| `UNAUTHENTICATED` | 401 | Missing, invalid or expired token |
| `FORBIDDEN` | 403 | Not allowed in this tenant |
| `NOT_FOUND` | 404 | — |

New codes are added here in the same merge request that introduces them.

## Contract workflow

1. A frontend engineer drafts a feature's endpoints in `openapi.yaml`, in the same merge request as the screens.
2. A backend engineer reviews within one working day: naming, feasibility, errors, anything the engine can't do.
3. Merging freezes the contract for that feature. Later changes need one frontend and one backend approval, plus the lead.
4. Backend implements it; Schemathesis fails the pipeline if responses don't match.
5. The feature switches from mock to real API; its scenario mocks move into tests.

Contracts go over one feature at a time, weekly at the latest. Backend starts in week one on work no screen defines: schema, double-booking guard, lifecycle, tenancy.
