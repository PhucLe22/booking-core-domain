# Architecture

One Flask application split into core modules, one PostgreSQL database with per-tenant row-level security, and one worker that delivers events and runs timers. On the frontend, shared packages that every product reuses, and two reference apps built from them. Everything runs in containers.

## Stack

| Area | Choice |
| --- | --- |
| Backend | Python 3.12+, Flask, modular monolith |
| Database | PostgreSQL |
| Background work | One worker using PostgreSQL as its queue (outbox and timers) |
| Frontend | React, TypeScript, Vite, shadcn/ui, TanStack Query, TanStack Router |
| API contract | One OpenAPI 3.1 file, written UI-first by Frontend |
| Client and mocks | Orval generates typed hooks, Zod schemas and MSW mocks from the contract |
| Rules | JSONLogic, evaluated in Python and in the browser |
| Auth | JWTs from our existing auth service, verified by the core |
| Analytics and errors | PostHog and Sentry, hosted |
| Code and CI | Private GitLab, GitLab CI, GitLab container and package registries |
| Demo hosting | Our physical server, Docker Compose, Caddy |
| Production hosting | AWS or Azure |

## Core modules

Each module owns its data and talks to others only through its public service.

| Module | Owns |
| --- | --- |
| Tenancy | Tenants, account settings, branding, timezone |
| Users | People, roles, groups, permissions |
| Resources | Sites, resource types, resources, custom field values |
| Availability | Hours, blackouts, slot size, buffers, free/busy search |
| Booking | Bookings, the lifecycle, booking history |
| Rules | Rule definitions, evaluation, decision traces |
| Pricing | Price plans, rates, credits (stub until after December) |
| Configuration | Versioned settings, field definitions, presets |
| Notifications | Templates per event and channel (email first) |
| Events | Outbox, delivery; later webhooks and automations |
| Analytics | Turns events into metrics |

Later: **Payments** (plugs into the lifecycle's payment hook), files and media, search.

## Repo layout

```text
booking-core/
├── CLAUDE.md                 start here
├── core/api/                 Flask app: modules/, worker/, migrations/, tests/
├── web/                      pnpm workspace: shared packages and the two apps
│   ├── packages/             shared frontend: api-client, ui, custom-fields, rules-editor, booking-ui, app-kit
│   ├── apps/
│   │   ├── console/          operators: sites, resource types, fields, rules, flows, approvals
│   │   └── member/           members: search, book, my bookings, check in, cancel
│   └── mock-server/          local stand-in API: runs the apps' shared mock data as one real server, so console and member see each other's changes before core/api exists for a feature
├── seeds/                    demo tenants as configuration data
├── contracts/openapi.yaml    the API contract
├── infra/                    Dockerfiles, Compose files, Caddyfile
├── docs/                     these docs
└── .gitlab-ci.yml            the pipeline
```

- **No product code anywhere** ([core-boundaries.md](core-boundaries.md)).
- **Two apps, like a real product:** every product has an operator console and a member app, used by different people on different domains. Two consumers also expose hidden coupling in the packages, and the member app never ships console code.
- **The apps are treated like a product:** they use only package entry points and the public API. No demo-only endpoints. If they need something, it goes into a package or the API, where products get it too.
- **Seeds are configuration, never code.**
- **The console is not throwaway:** configuring types, fields, rules and flows is the same for every product, so its building blocks live in `web/packages/`.
- **`web/mock-server` is dev-only and never deployed:** it runs the exact same scenario logic as each app's in-browser MSW mocks, but as one real local server, so console and member can share data before `core/api` implements a feature. See [frontend.md](frontend.md)'s "Shared mock server".

## How products use the core

The core runs as a **service**: its own deployment and database. Products never run core code in their own app.

| Connection | From → to | Used for |
| --- | --- | --- |
| User's JWT | Product frontend → core API | Bookings, availability, resources, rules, config |
| User's JWT | Product frontend → product API | Product-only features: memberships, invoices |
| Service token | Product API → core API | Applying presets, creating resources, reading bookings |
| Signed webhook | Core worker → product API | Reacting to `booking.confirmed`, `booking.completed`, … |

A visitor who books without registering still authenticates: the auth service issues them a short-lived JWT (no password, minimal claims) instead of the usual sign-in token. The core treats it like any other user's JWT — there's no unauthenticated connection to the core API. See [backend.md](backend.md)'s "Auth" section.

| A product needs to… | How |
| --- | --- |
| Store product-only data | Its own backend and database; the core never sees those tables |
| Add a field to a core object | A custom field defined by its preset, never a core schema change |
| Set up a new customer | Apply its presets through the core config API |
| Do something the core can't | Request a core change in this repo; meanwhile use an event listener or its own backend |

On the frontend, a product installs the `@booking-core/*` packages from our GitLab npm registry, sets up the client with `app-kit`, overrides the theme tokens, and builds its own screens from core hooks and components. Examples: [examples/product-app/](examples/product-app/).

Packages follow semantic versioning with a changelog. Breaking changes only come in a major version; each `api-client` version states which core API version it needs.

**Before the first product starts** (after December), the core needs: webhook delivery to outside subscribers with signatures and retries, service tokens with scopes, a stable `/api/v1`, and published packages and images.
