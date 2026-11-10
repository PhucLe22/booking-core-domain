# Glossary

| Term | Meaning |
| --- | --- |
| **Tenant** | One paying customer organisation, e.g. GreenDesk Co-working. Tenants never see each other's data. |
| **End user / member** | A person who books through a tenant's setup. |
| **Guest** | A tenant role for a person who books without registering. Still a core user with a JWT — issued by the auth service without a password — just with a lighter identity and fewer permissions than `member`. |
| **Site** | A physical location of a tenant, with its own timezone and opening hours. |
| **Resource type** | A template for bookable things (desk, meeting room, phone booth), with custom fields and policies. |
| **Resource** | One bookable thing of a type, e.g. Phone Booth 1. |
| **Booking** | A claim on a resource for a time range. |
| **Pipeline** | The fixed sequence of checks a booking request goes through before it's saved. |
| **Lifecycle** | The fixed booking statuses and the only moves allowed between them. |
| **Transition** | One move in the lifecycle (confirm, check in, cancel), always run through `transition()`. |
| **Policy** | A customer setting that shapes the lifecycle: payment, approval, check-in, cancellation, no-show. |
| **Rule** | A condition and an effect evaluated in the pipeline, e.g. "guests may book at most 2 hours". |
| **Event** | A permanent record that something happened, e.g. `booking.confirmed`. |
| **Outbox** | Where events are saved together with the change, then delivered by the worker. |
| **Config version** | One saved version of a tenant's settings or rules. Bookings remember the version they were made under. |
| **Preset** | A bundle of configuration that sets up a product for a new tenant in one click. |
| **Product / vertical** | A product built on the core (co-working, workplace). Lives in its own repo, never in this one. |
| **Reference apps** | `web/apps/console` (operators configure the core) and `web/apps/member` (members book): two apps in this repo that demonstrate and test the core. |
| **Seed** | A demo tenant defined as configuration data in `seeds/`, applied through the public API. |
| **Contract** | `contracts/openapi.yaml`, the API description both sides follow. |
| **Mock mode** | A frontend app running against generated mock APIs instead of the real backend. |
