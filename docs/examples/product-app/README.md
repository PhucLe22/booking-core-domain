# Using the core in a product app

How a product repo (e.g. co-working) uses the core's frontend packages. Names of hooks and components are illustrative; the real ones come from the contract and the packages.

| File | Shows |
| --- | --- |
| `npmrc.example` | Installing `@booking-core/*` from our GitLab npm registry (save as `.npmrc`) |
| `app-setup.tsx` | Starting the app with `app-kit` and pointing the client at the core API |
| `theme.css` | Applying the product's brand over the core theme tokens |
| `book-a-meeting-room.tsx` | A product screen built from core hooks and components |

Install: `pnpm add @booking-core/app-kit @booking-core/api-client @booking-core/ui @booking-core/booking-ui @booking-core/custom-fields @booking-core/rules-editor`
