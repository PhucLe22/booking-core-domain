# Rules

A rule is **scope + condition + consequence + priority**: what the condition compares, and what happens when it matches — chosen directly, not inferred from a pipeline position. Example: [examples/rule.json](../examples/rule.json).

| Part | Values |
| --- | --- |
| Scope | Tenant, site, resource type or resource |
| Condition (`when`) | JSONLogic over a fixed context: `booking`, `resource`, `user`, `user.groups`, `time`, `usage` |
| Consequence | `deny` or `require_approval` — what happens when the condition matches (`pricing` may be added later) |
| Priority | Higher runs first |

An earlier version of this model had a 3-value `stage` (`eligibility`/`limits`/`approval`) with a separate `effect` field. Both are gone: `eligibility` and `limits` were never functionally different (both denied), so collapsing them into one `deny` consequence loses nothing and removes a confusing choice that looked meaningful but wasn't.

## How rules are evaluated

1. Load the published rules for the booking's scope, most general first: tenant → site → resource type → resource.
2. Build the context from the fixed keys above.
3. Evaluate every enabled rule's condition, highest priority first, and collect the consequences: `deny` matches become reasons the booking is blocked; any `require_approval` match sets the approval flag.
4. Resolve conflicts: deny beats allow; ties go to the more specific scope.
5. Return a decision and a **trace** naming every rule that matched and what it did.

The same rules run in Python (the server's decision) and in the browser (admin previews). A shared file of example rules and expected results runs against both evaluators in the pipeline, so they can never disagree silently.

## The condition builder's clause types

The console's condition builder composes a rule's `when` as an AND of clauses over the fixed context, rather than hand-written JSONLogic. Each clause type maps onto a distinct part of that context:

| Clause | Expresses | Compiles to |
| --- | --- | --- |
| Member is in group | Membership in one or more groups, with an is / is not toggle | `in`/`or` over `user.groups`, optionally negated |
| Booking duration | A numeric comparison against the booking's length | A comparison over `booking.durationMinutes` |
| Booking start hour | A numeric comparison against the booking's start hour | A comparison over `booking.startHour` |
| Booking starts within/after | How soon (or how far out) the booking starts, in minutes or days | A comparison over `booking.startsInMinutes` |
| Max active bookings | Whether the member is already at (or over) a cap of N active bookings starting within the next M days — e.g. "max 2" denies a 3rd attempt once 2 are already upcoming | A comparison over a windowed count of `usage.activeBookingStarts` |

A rule wanting both a minimum and a maximum notice period (e.g. "at least 1 hour, at most 30 days ahead") adds two separate rules, one per bound — a single AND-combined condition can't express an either/or.

There's no real member/group data model yet — every real booking evaluates with `user.groups` hardcoded to `['guest']` (`bookingsOperations.ts`, demo has one seeded member and no membership/group management screen). The group clause's value picker is constrained to that one real group rather than free text, since any other value can never match — revisit once a real membership/group system exists.

## Limits

- No loops, no external calls inside conditions, and a cap on rules per consequence. Anything beyond that is an extension.
- AI-written rules return rule JSON, which is validated against the rule schema, previewed, and published by a person. The model never publishes.

## Planned: impact analysis before publishing

Today's preview evaluates a rule against one synthetic sample booking the admin fills in by hand — useful for checking the rule's logic, but it gives no sense of how many real bookings a rule would actually affect once published.

Planned addition: before publishing, also evaluate the candidate rule against the tenant's real existing/upcoming bookings in scope, and report how many (and optionally which) would be affected. This is purely informational, reporting what the rule *would* do if those same booking patterns were attempted again — publishing a rule never retroactively re-evaluates or changes a booking already made, same as resource-type config changes (see [configuration.md](configuration.md)). Not yet implemented.
