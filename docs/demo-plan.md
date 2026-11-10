# December demo plan

On **Tuesday, Dec 15, 2026**, we show the boss one thing: **a customer reshapes the booking system without us touching code.** Every task proves that or supports it; anything else waits until after December.

The demo runs on the reference apps. Its strongest moment: three seeded businesses (a co-working space, a company office and a sports court) running on the same core with configuration alone.

## Demo story (about six minutes)

| # | Step | What the boss sees | Time |
| --- | --- | --- | --- |
| 1 | Set up a space | Admin creates a "Phone booth" type with a custom field and three booths, no deploy | 1 min |
| 2 | Book it | Member searches, books, gets a confirmation | 1 min |
| 3 | Walk the lifecycle | Check in, complete; cancel another; a third becomes a no-show; the booking timeline | 1.5 min |
| 4 | Change rules live | "Guests max 2 h; over 4 h needs approval" blocks the next booking, with the reason | 1.5 min |
| 5 | Change the flow live | Meeting rooms switch from instant to approval; admin approves | 30 s |
| 6 | AI moment | Plain-language rule → structured rule → preview → publish | 30 s |
| 7 | Proof it holds | Two browsers book the same desk at the same second; one wins | 30 s |

## Scope

| In the demo | After December |
| --- | --- |
| Two seeded tenants; admin and member roles | Self-signup, plans, entitlements |
| Sites, resource types with custom fields, resources | Floor plans, deeper hierarchies |
| Availability: hours, blackouts, slot size, buffers | Recurring bookings, country holidays |
| Full lifecycle; the payment hook does nothing | Payments |
| 5–6 rule types with "explain why" | Visual rule builder |
| Flow config per resource type | — |
| Email notifications | SMS, push, editable templates |
| Plain-language → rule | Booking assistant chat |
| Product tracking in every screen | Customer space-analytics dashboard |

## Team

| Role | People | Owns |
| --- | --- | --- |
| Lead | 1 | Reviews and decisions only, no product code: approves doc and decision-log changes; reviews `core/`, `web/packages/` and `contracts/`; sets sprint priorities and cuts; owns the demo script and communication with the boss |
| Frontend | 1 | Shared packages, `web/apps/console` and `web/apps/member`, the API contract, mocks, the tracking plan; DevOps with Backend |
| Backend | 3 | Core modules, worker, database and migrations, seeds; DevOps with Frontend |
| AI | 1 | Rule engine with "explain why"; plain-language → rule |

Frontend and Backend engineers split work by feature each sprint rather than owning fixed areas.

## Timeline

| Sprint | Dates | Build | Done when |
| --- | --- | --- | --- |
| Setup | Oct 21–23 | Decisions, repo, pipeline skeleton | Docs agreed |
| 1 · Foundations | Oct 26–Nov 6 | Apps on mocks, schema, tenancy, resource types | A new resource type shows up for members |
| 2 · Lifecycle | Nov 9–20 | Lifecycle, booking screens, timeline, approvals; first mocks swapped for real | Full lifecycle works; checkpoint demo Nov 20 |
| 3 · Rules + AI | Nov 23–Dec 4 | Rules, flow config, emails, plain-language rules | All seven steps run end to end |
| 4 · Polish | Dec 7–11 | Bugs, concurrency demo, rehearsals | Freeze Dec 10; backup video recorded |
| Demo | Dec 15 | Live on the demo server | — |

## Cut order if we slip

1. Email notifications → show the booking timeline instead.
2. AI plain-language rules → rules edited as a form.
3. Quota rule → keep duration, window, approval.
4. Approval timeout → manual approve and reject only.
5. Custom fields → fixed fields only.

**Never cut:** the lifecycle, rules with "explain why", the flow config switch, double-booking protection.
