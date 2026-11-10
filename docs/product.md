# Product

We build one **booking core** and sell **products** on top of it as subscriptions. The core is our engine; customers buy finished products and configure them, without us writing code for them.

## Products

| Product | Buyer | When |
| --- | --- | --- |
| Booking core | Our own product teams; partners via API later | First, in this repo |
| Co-working booking | Co-working operators | First product, after the December demo, in its own repo |
| Workplace / building management | Facilities and HR teams, building owners | Second product |
| Other verticals (clinics, sports courts, venues, equipment) | Various | Only after two products work |

The core is not sold on its own at first. It is proven by two reference apps and seeded demo tenants modelled on real businesses: a co-working space, a company office and a sports court. Products use released versions of the core; they never fork or copy it.

Two habits keep the core honest without a product pushing on it:

- **Seeds as proof:** every seed tenant runs on configuration alone. If one needs special code, the core is missing a capability.
- **Real rules as the backlog:** collect booking, pricing and cancellation rules from a few design-partner operators. Each must be expressible through configuration; the ones that aren't become core work.

## Customers configure, we don't code

New customers and new requirements should not need code changes. That only works inside known axes of variation; making everything configurable produces a home-made programming language nobody can use.

The rule: **configure the common, extend the rare, code the new.**

| Level | What changes | Who | Code change? |
| --- | --- | --- | --- |
| 1. Settings | Values on existing behaviour: hours, booking window, branding | Customer admin | No |
| 2. Rules | Combinations of predefined conditions and effects | Customer admin | No |
| 3. Schema extension | New resource types, custom fields, booking forms | Customer admin | No |
| 4. Extensions | Behaviour we never anticipated: webhooks, API | Customer developer or partner | No change to the core |
| 5. New capability | A new axis of variation | Us | Yes, and it becomes configurable for everyone |

## Axes of variation

1. **What** is booked: resource types, fields, capacity, site → resource hierarchy.
2. **When** it's available: hours, holidays, blackouts, buffers, slot size.
3. **Who** may book: roles, groups, eligibility rules.
4. **How** it's booked: instant or approval, duration limits, advance window, quotas.
5. **What it costs:** price plans, rates, credits, deposits, refunds.
6. **What happens after:** check-in, no-shows, notifications, automations.
7. **How it looks:** branding, language, terms, forms.

A request outside these axes is a new option on an existing axis or an extension. It becomes a new axis only when three or more customers need it.
