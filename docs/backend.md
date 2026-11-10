# Backend guide

For anyone working in `core/`. Shared rules live in the root [CLAUDE.md](../CLAUDE.md); API rules in [api.md](api.md); domain behaviour in [domain/](domain/).

## Structure

One Flask app in `core/api/`. Each core module is a package under `core/api/modules/` (tenancy, users, resources, availability, booking, rules, pricing, config, notifications, events). The worker lives in `core/api/worker/` and runs from the same image.

Each module has:

| File | Holds |
| --- | --- |
| `api.py` | Flask blueprint: routes only, no business logic |
| `service.py` | The public interface other modules may call |
| `models.py` | SQLAlchemy models, private to the module |
| `schemas.py` | Pydantic request and response models, mirroring the contract |
| `events.py` | Events the module emits |

## Rules

- A module may import another module's `service.py` only. import-linter enforces it.
- A route parses input, calls **one** service function, and returns a response model.
- A service function runs in one transaction; any change writes its events to the outbox in that same transaction.
- Booking status changes only through `transition()`.
- Keep functions small and single-purpose; tests ship in the same merge request.
- Migrations: Alembic, run as a separate deploy step, never at app start. Backward compatible for one release: add, deploy, remove later.
- Logs: JSON to standard output, with request id and tenant id on every line.

## Libraries

| Concern | Choice |
| --- | --- |
| Database | SQLAlchemy 2, Alembic |
| Validation | Pydantic v2; `jsonschema` for custom fields |
| Rules | A JSONLogic evaluator |
| Auth | PyJWT |
| Contract checks | Schemathesis |
| Boundaries | import-linter |
| Lint and format | ruff |
| Tests | pytest |
| Serving | Gunicorn behind Caddy |

## Data and tenancy

- Every table has `tenant_id`, filtered by row-level security policies. Example: [examples/sql/tenant-isolation.sql](examples/sql/tenant-isolation.sql).
- After verifying the JWT and the user's membership in the requested tenant, the API sets the tenant for the transaction (`SET LOCAL app.tenant_id`).
- The app connects as a role that does **not** own the tables; owners bypass row-level security unless it's forced.
- Double bookings are impossible: an exclusion constraint on resource and time range rejects the second of two racing requests, and the API returns `SLOT_TAKEN`. Example: [examples/sql/no-double-booking.sql](examples/sql/no-double-booking.sql). Shared-capacity spaces use a row-locked counter instead.
- IDs are UUIDv7. Timestamps are `timestamptz`.

| Table | Holds |
| --- | --- |
| `resource_types` | Field definitions (`field_defs`), policies (`flow_config`), `version` |
| `resources` | Custom field values in `attributes` (JSONB, GIN index), `definition_version` |
| `config_versions` | Every draft and published version of settings and rules |
| `bookings` | `during` (time range), `status`, `payment_status`, `applied_config` |
| `booking_events` | Booking history: from, to, actor, reason |
| `attribute_history` | Previous custom field values |
| `outbox` | Events waiting for delivery |
| `scheduled_jobs` | Timers: no-shows, approval timeouts, payment-hold expiry |

## Auth

Users sign in through our existing auth service, which issues JWTs. The core never handles passwords.

- **Verify every token:** signature, `exp`, `iss`, `aud`. Prefer asymmetric keys (RS256 or ES256) from the auth service's JWKS endpoint. With a shared secret (HS256), keep it in the server's `.env` and plan a move to asymmetric keys.
- **Map the user:** `sub` maps to a core user, created on first sight from the token's claims.
- **Tenant and role come from the core:** the user's membership in the tenant named by `X-Tenant-Id`. One person can belong to several tenants.
- **Roles per tenant:** `owner`, `admin`, `staff`, `member`, `guest`; optionally scoped to a site.
- **Guest (no-account) booking:** a person who books without registering still needs a token — the auth service issues a short-lived JWT for them (minimal claims, no password) the same way it does for a registered sign-in. The core maps it to a core user on first sight exactly as any other token, tagged with the `guest` role. The core never has an unauthenticated path; "no account" is handled upstream by the auth service, not by relaxing the core's auth requirement.
- **Behind an adapter:** token verification sits behind one `AuthAdapter` class, so changing providers touches one place.
- **Service tokens** for product backends (after December) are JWTs with a `scope` claim.

## Engine

### `transition()`

Looks up the move in the lifecycle table ([domain/booking.md](domain/booking.md)) and raises `INVALID_TRANSITION` if it's not allowed. Then it runs the hooks for the target status (rules, payment, check-in window), which may deny with reasons. Finally it updates the status, writes a `booking_events` row and adds the event to the outbox, all in the request's transaction. The payment hook has one implementation for December: `NoPayment`.

### Rules

Evaluation follows [domain/rules.md](domain/rules.md). Published rule sets are cached per tenant and refreshed on `config.published`.

### Worker

- **Outbox delivery:** picks up undelivered events with `FOR UPDATE SKIP LOCKED`, hands each to its subscribers, and marks it delivered. Failures retry with growing delays and are parked with an alert after a set number of attempts.
- **Timers:** runs due `scheduled_jobs`, each through `transition()`.
- **Duplicates:** each subscriber records processed event ids and skips repeats.

## Testing

Tests are written together with the code, in the same merge request. Backend functions are small and fully specified, so tests are cheap and catch the costliest bugs early. Agents write them as part of the task.

| Area | Must have |
| --- | --- |
| Lifecycle | Every allowed move works; every other move raises `INVALID_TRANSITION`; each move writes history and one event |
| Rules | The shared example file passes; deny beats allow; traces are correct |
| Double booking | Two parallel requests for one slot: exactly one succeeds (real PostgreSQL) |
| Tenancy | Tenant A can't read or change tenant B's data through any endpoint |
| Auth | Expired, wrongly signed and wrong-audience tokens are rejected; non-members get `FORBIDDEN` |
| Time | Daylight-saving changes and midnight in the site's timezone |
| Contract | Responses match `openapi.yaml` (Schemathesis) |
| Worker | A duplicate event is processed once; failures retry |
| Seeds | Every seed tenant applies through the public API |
