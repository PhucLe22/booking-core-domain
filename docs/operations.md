# Operations

For anyone working on Docker, the pipeline, the demo server or deploys. The files themselves live in `infra/` and `.gitlab-ci.yml`.

## Environments

| Environment | Where | Data | Deployed |
| --- | --- | --- | --- |
| Local | Laptops: API, worker, database in Compose; apps run natively | Seed data, reset at will | By hand |
| Staging (demo) | Our internal physical server, by IP address; Docker Compose, Caddy | Seeded demo tenants | Every merge to `master` |
| Production | AWS or Azure | Real tenants | Tagged releases |

**Demo server containers:** `caddy`, `console`, `member`, `api`, `worker`, `postgres`, and a GitLab Runner. **Outside services:** the existing auth service, PostHog, Sentry, and our GitLab (code, pipeline, container and package registries).

## Images

| Image | Built from | Notes |
| --- | --- | --- |
| `api` | `core/api/` | The worker runs from the same image with a different command |
| `console`, `member` | `infra/web/Dockerfile` with `APP=console` or `APP=member` | One recipe, one nginx config, one runtime config script for both |

- Images are tagged with the commit SHA and pushed to the GitLab container registry.
- Frontend images read environment values at container start (`infra/web/40-runtime-config.sh` writes `config.js`), so one image runs in every environment.
- The demo server is on the internal network and reached by its IP address. Caddy (`infra/Caddyfile`) serves the member app on port 3000 and the console on port 3001, and each port forwards `/api/*` to the API. The browser talks to one address per app, so there's no cross-origin setup and `API_URL` stays empty.
- It runs on plain HTTP inside the office network. Before anyone reaches the server from outside, switch to domain names, which gives automatic HTTPS.

## Cloud-ready rules

- All configuration comes from environment variables.
- Containers keep no state; uploaded files (later) go to object storage.
- Logs go to standard output.
- Migrations run as a separate step.

| Piece | Demo server | AWS | Azure |
| --- | --- | --- | --- |
| HTTPS and routing | Caddy (HTTP by IP for now) | Load balancer + Certificate Manager | Application Gateway or Front Door |
| Apps, API, worker | Docker Compose | ECS on Fargate | Container Apps |
| Database | PostgreSQL container | RDS for PostgreSQL | Azure Database for PostgreSQL |
| Images | GitLab container registry | GitLab or ECR | GitLab or Azure Container Registry |
| Secrets | `.env` on the server | Secrets Manager | Key Vault |

## Pipeline

Defined in `.gitlab-ci.yml`.

**On every merge request:**

1. Lint and types: ruff; Biome and `tsc`.
2. Contract: Spectral lints `openapi.yaml`; the generated client must match what's committed.
3. Boundaries: import-linter; Biome import rules (apps use only package entry points, apps don't import each other, packages don't import apps); banned product words outside `seeds/`.
4. Tests: backend against real PostgreSQL; frontend unit and component tests.
5. API and seeds: Schemathesis against the running API; every seed tenant applies cleanly.
6. All three images build.

A merge request can't be merged until the pipeline passes.

**On merge to `master`:** images are pushed, then the GitLab Runner on the demo server pulls them, runs migrations as a one-off container, restarts the services and checks `/api/healthz`. A runner on the server means no SSH access from outside.

**Rollback:** re-run the deploy job from the previous commit's pipeline.

## Secrets

- Pipeline secrets are masked, protected GitLab CI/CD variables.
- Server secrets live in `/srv/booking-core/.env`, readable only by the deploy user.
- Never in git.

## Backups and runbooks

- The database is backed up nightly and copied off the server. A restore is tested before the demo.
- Every manual change to the server is written down in `docs/runbooks/` first. Each runbook is a future script.
