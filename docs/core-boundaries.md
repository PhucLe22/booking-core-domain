# Core boundaries

The core never knows which product it is running. Code like `if product == "coworking"` or `if tenant == "GreenDesk"` turns the core into one product with extra steps. Under deadline pressure it always looks like the fastest fix, so this is the rule most worth defending.

## What leaking looks like

| Leaking into the core | Do this instead |
| --- | --- |
| "If co-working, require payment before confirm" | Payment policy on the resource type: charge on submit |
| "If workplace, hide prices" | A setting `pricing.enabled: false`, turned on by the product's preset |
| "If tenant is GreenDesk, allow 3-hour bookings" | A rule GreenDesk configures |
| A `member_plan` column on the core booking table | A custom field defined by the product's preset |
| "If the type is desk, skip approval" | Flow config on the Desk type: confirmation instant |
| Invoice logic inside the Booking module | The product's backend listens to `booking.completed` |

## Why it hurts

- Every product-specific branch must be respected by every future change, and they multiply.
- Behaviour hidden in code can only be changed by us, which breaks the "no code for new requirements" promise.
- The second product starts by untangling the first one's code instead of reusing the core.

## How we avoid it

1. **Name the behaviour, not the customer.** "Co-working needs up-front payment" becomes "payment timing is configurable".
2. **Presets carry the product.** The core only reads settings.
3. **Products live in their own repos and depend on the core, never the reverse.**
4. **Banned words, checked in the pipeline:** `coworking`, `co_working`, `workplace`, `office`, `member_plan` and customer names, anywhere except `seeds/`.
5. **Review question on every core change:** "Would this make sense for a clinic or a sports court?" If not, it belongs in a preset or a product.
6. **Three-customer rule:** one customer's request becomes a rule or an extension; a new core setting only when three customers need it.
7. **An unavoidable shortcut before a deadline** goes behind a named setting with a cleanup ticket, never behind a product or tenant check.
