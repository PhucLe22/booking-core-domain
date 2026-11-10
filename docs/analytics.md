# Analytics and tracking

We build product and UX analytics first, to answer the boss's questions: how many people use our products, how long they stay, whether they like it, and what blocks them. Customer-facing space analytics (utilisation, occupancy, no-shows) comes later, from the same events.

## What we measure

| Question | Measure | How we capture it |
| --- | --- | --- |
| How many users? | Daily, weekly, monthly active users by tenant, role and app; new vs returning | Every tracked event carries user, tenant, role and app |
| How long and how often? | Session length, sessions per week, retention after 1, 4 and 12 weeks | Session tracking; weekly retention groups |
| Do they like it? | A 1–5 score after key tasks, a quarterly recommend score, retention | In-app surveys, at most once every few weeks per person |
| What blocks them? | Funnel drop-off, searches with no results, rule denials, errors, time to finish | Funnels, error tracking, session replay, monthly interviews |

## Funnels

1. **Member booking:** open app → search → pick a resource → submit → confirmed.
2. **Tenant setup:** create site → add resource type → add resources → first member booking (an activated tenant).
3. **Rule change:** open rules → edit → preview → publish.

## How we track

- **Tools:** PostHog (events, funnels, retention, replay, surveys) and Sentry (errors), both hosted.
- **Two sources:** apps send screen actions; the worker forwards core events from the server. Business numbers come from server events, so ad blockers can't skew them.
- **Identity:** identify the user after login. Every event carries `tenantId`, `role` and `app` (`console` or `member`).
- **Naming:** screen events are `object_action`, snake_case, past tense (`booking_search_submitted`). Core events keep their dotted names (`booking.confirmed`).
- **Privacy:** session replay masks all inputs and member names and emails; no personal data in event properties.
- **Separate projects** for local, staging and production.
- **Monthly review:** 30 minutes on the numbers plus three to five short user interviews.
- **Every new screen** adds its events to the tracking plan in the same merge request.

## Tracking plan

| Event | Sent when | Properties | Funnel |
| --- | --- | --- | --- |
| `booking_search_submitted` | Member searches | siteId, resourceTypeId, date, resultsCount | Member booking |
| `resource_selected` | Member opens a result | resourceTypeId, position | Member booking |
| `booking_submitted` | Member presses Book | resourceTypeId, durationMinutes | Member booking |
| `booking.confirmed` (server) | Lifecycle confirms | path, minutesSinceSearch | Member booking |
| `booking.denied` (server) | A rule blocks | ruleIds | What blocks them |
| `resource_type_created` | Admin saves a type | fieldCount | Tenant setup |
| `resource_created` | Admin adds a resource to a type | resourceTypeId | Tenant setup |
| `resource_type_flow_config_updated` | Admin saves a type's flow config | resourceTypeId, confirmation | Tenant setup |
| `rule_published` | Admin publishes a rule | consequence, previewUsed | Rule change |
| `rule_ai_draft_generated` | Admin generates a rule draft from plain language | consequence | Rule change |
| `survey_answered` | Member answers the post-booking survey | score | Do they like it |
| `my_bookings_viewed` | Member opens "My bookings" | resultsCount | — |
| `booking_calendar_viewed` | Member opens the booking calendar | — | — |
| `booking_checked_in` | Member checks in | resourceTypeId | — |
| `booking_cancelled` | Member cancels a booking | resourceTypeId | — |
| `booking_approved` | Admin approves a pending booking | resourceTypeId | Admin approvals |
| `booking_rejected` | Admin rejects a pending booking | resourceTypeId | Admin approvals |
| `booking_completed` | Admin ends a checked-in booking early | resourceTypeId | — |
| `booking_no_show` | Admin marks a confirmed booking as no-show | resourceTypeId | What blocks them |
