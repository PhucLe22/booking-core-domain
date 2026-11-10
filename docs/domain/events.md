# Events

Every change in the core produces an event. Notifications, automations, webhooks, analytics and booking history **listen to events** instead of being called directly. That's what lets us add features without touching booking code.

## The outbox

A change and its event are saved in the **same database transaction**. A worker then delivers each event to its subscribers.

- **Nothing is lost:** if the change saved, the event exists; if the save failed, there is no event.
- **Subscribers can't break bookings:** a slow email server or broken webhook never blocks a booking; delivery retries in the background.
- **New subscribers need no core changes.**

## What every event carries

| Field | Example |
| --- | --- |
| Name | `booking.confirmed`, past tense: a fact, not a command |
| Tenant | The tenant's id |
| Subject | Booking 8841 on Room A |
| Actor | A user, or `system` for timers |
| Time | When it happened |
| Changes | Status `pending_approval` → `confirmed` |
| Config version | The flow config and rule set versions in force |

Example: [examples/event.json](../examples/event.json).

## Event catalogue

| Event | When | Typical subscribers |
| --- | --- | --- |
| `booking.requested` | A member submits a request | Analytics |
| `booking.denied` | A rule blocks the request (nothing is saved) | Analytics |
| `booking.awaiting_payment` | Payment needed | Payments, notifications |
| `booking.approval_requested` | Approval needed | Notification to approver |
| `booking.confirmed` | Booking confirmed | Email, calendar, analytics, webhooks |
| `booking.rejected` | Approver rejects | Email, analytics |
| `booking.expired` | Payment fails or times out | Email, analytics |
| `booking.checked_in` | Member checks in | Analytics |
| `booking.completed` | Booking ends | Analytics; invoicing later |
| `booking.cancelled` | Member or admin cancels | Email, analytics |
| `booking.no_show` | Check-in window passes | Email, strike counter, analytics |
| `resource.created`, `resource.updated` | Admin changes a resource | Audit, analytics |
| `config.published` | Admin publishes settings or rules | Audit, cache refresh |

## Ground rules

1. Events are never edited or deleted; a correction is a new event.
2. Subscribers must cope with receiving the same event twice.
3. Event names and fields are a contract: change them like an API, with a version.
4. To react to something, subscribe to its event. Never ask the Booking module to call you.
