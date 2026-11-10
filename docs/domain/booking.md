# Booking: pipeline, lifecycle, policies

A booking request is first **evaluated** by the pipeline, then **lives** in the lifecycle. Both are the same for every product and tenant; tenants change their behaviour through settings, rules and policies.

## The pipeline

Every request runs through the same seven steps, in this order:

| Step | Job | Tenant configures | Changes data? |
| --- | --- | --- | --- |
| 1. Validate request | Fields present and valid | Booking form, custom fields | No |
| 2. Check availability | Resource free for that time | Hours, blackouts, buffers, slots | No |
| 3. Eligibility rules | May this person book this resource? | Who may book what | No |
| 4. Limit rules | Duration, advance window, quotas | Limits | No |
| 5. Approval rules | Instant or needs approval? | Approval conditions | No |
| 6. Price | What it costs (after December) | Price plans, credits | No |
| 7. Save and start the lifecycle | Create the booking, run the submit transition, emit the event | — | **Yes** |

- **The order is how the engine evaluates, not how admins configure.** Admins edit each section independently, in any order.
- **Why it's fixed:** later steps depend on earlier ones, members get the most useful reason first, cheap checks run first, and results stay predictable.
- **Steps 1–6 only decide**, so they can run as a dry run: "would this booking be allowed?"
- **Every "no" names the setting or rule that stopped it**, shown to the member and tracked.
- **Payment is not a step.** It's a lifecycle policy (below).

## The lifecycle

Nine fixed statuses. Tenants never add statuses; their policies switch optional paths on or off. Tenants may rename the labels members see.

| Status | Kind | Meaning |
| --- | --- | --- |
| `awaiting_payment` | Optional | Waiting for payment; only when the payment policy needs it |
| `pending_approval` | Optional | Waiting for an approver; only when approval rules require it |
| `confirmed` | Main | Holds the slot |
| `checked_in` | Main | The member arrived |
| `completed` | End | Ended normally |
| `expired` | End | Payment failed or timed out |
| `rejected` | End | An approver rejected it |
| `cancelled` | End | Member or admin cancelled |
| `no_show` | End | No check-in within the window |

`submitted` is the entry point (pipeline step 7), not a stored status.

### Allowed moves

| From | Move | To | Triggered by | What runs |
| --- | --- | --- | --- | --- |
| submitted | `require_payment` | awaiting_payment | Payment policy | Payment hold or charge |
| submitted, awaiting_payment | `require_approval`, `paid` | pending_approval | Approval rules | Approver notified |
| submitted, awaiting_payment, pending_approval | `confirm`, `paid`, `approve` | confirmed | System or approver | Confirmation, calendar update |
| awaiting_payment | `payment_failed`, timeout | expired | Payment provider or timer | Slot released |
| pending_approval | `reject` | rejected | Approver | Money released, member told why |
| awaiting_payment, pending_approval, confirmed | `cancel` | cancelled | Member or admin | Cancellation policy, refund if any |
| confirmed | `check_in` | checked_in | Member (if `selfCheckInAllowed`) or admin | Only if check-in is `required`, and only inside the check-in window |
| confirmed | `no_show` | no_show | Timer | No-show policy: release, fee or strike |
| checked_in | `complete` | completed | Timer or check-out | Usage recorded; charge if pay-after-use |

Every move goes through one `transition()` function. It runs the rules and the payment hook, writes history, and emits exactly one event, so a booking can never reach an impossible state.

## Policies per resource type

Each resource type carries policies for confirmation, check-in, cancellation and payment. Example: [examples/flow-config.json](../examples/flow-config.json).

Check-in has two independent flags: `required` (whether check-in is part of this resource type's lifecycle at all — i.e. whether no-shows get tracked) and `selfCheckInAllowed` (whether a member can check themselves in, default `true`). A staffed meeting room might require check-in but leave it to the front desk (`selfCheckInAllowed: false`); an unstaffed phone booth leaves both on. `selfCheckInAllowed` never restricts an admin's own check-in action — an operator can always check a booking in manually once `required` is true.

Each booking stores a copy of the policies it was made under. Changing settings never changes existing bookings.

### Payment is a policy, not a step

The payment policy says **which transition takes the money**. Payment status is tracked separately from booking status: `unpaid`, `held`, `paid`, `refunded`. Example: [examples/payment-policy.json](../examples/payment-policy.json).

| Tenant wants | `chargeOn` | What happens |
| --- | --- | --- |
| Pay before review | `submit` | Hold at submit, capture on approve, release on reject |
| Pay after approval | `confirm` | Approved → awaiting payment → confirmed once paid |
| Pay after use | `complete` | Card saved at submit, charged for actual usage on completion |
| Monthly invoice | `none` + invoice | Each completed booking adds a line to the month's invoice |
| Free (December demo) | `none` | The payment hook does nothing |

A new payment timing is a new `chargeOn` option, never a change to the pipeline or the lifecycle.
