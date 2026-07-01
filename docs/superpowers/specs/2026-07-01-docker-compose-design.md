# docker-compose extension — design

**Date:** 2026-07-01
**Status:** approved
**Extension:** #4 of the CampaignFlow ladder (after PySpark #1, Terraform landing zone #2, dashboard #3).

## Goal

Make the whole stack run with one command — `docker compose up` builds the
warehouse, exports the gold marts, and serves the Next.js dashboard over them.
This makes the CV line "runs locally via docker compose" literally true, with no
invented claims: it runs locally, and that is exactly what we say.

## Constraint that shapes the design

The dashboard imports its data at **build time**, not runtime:

```ts
// dashboard/app/page.tsx
import martsJson from "@/public/data/marts.json";
```

So `marts.json` must exist *before* `next build` runs. The compose topology must
guarantee the pipeline produces the marts before the dashboard builds. We do not
change the dashboard's static architecture; we order the services so the import
target is fresh.

## Scope

**In:**
- Two services — `pipeline` (Python) and `dashboard` (Node) — sharing one named
  volume for the marts hand-off.
- Production-like dashboard: `next build` then `next start` at container start,
  once fresh marts exist.
- A CI smoke-test job that brings the stack up and asserts it actually serves the
  fresh marts.
- README quickstart + roadmap update; HANDOFF update.

**Out (documented, not faked):**
- Azurite landing zone in compose — stays a separate documented step (extension
  #2's README section). The default compose path uses in-process generation, no
  blob emulator.
- PySpark / Databricks path in compose — the DuckDB pipeline is the default; the
  Spark fact remains a parity-tested extra, not part of `docker compose up`.
- A real orchestrator, streaming, or cloud deploy — unchanged from the project's
  standing "later" list.

## Topology and data flow

```
┌─────────────┐   writes /marts/marts.json    ┌──────────────┐
│  pipeline   │ ────────────────────────────▶ │  dashboard   │
│ python:3.12 │      (named volume: marts)     │  node:22     │
│             │                                │              │
│ run→export  │   depends_on: completed_ok     │ build→start  │
└─────────────┘ ─────────────────────────────▶ └──────┬───────┘
   exits 0                                        :3000 │ ▶ host :3000
```

- **`pipeline`** is a run-to-completion job: it builds the DuckDB warehouse,
  exports `marts.json` into the shared `marts` volume, then exits 0.
- **`dashboard`** starts only after `pipeline` finishes successfully
  (`depends_on: { pipeline: { condition: service_completed_successfully } }`),
  copies the fresh marts into `public/data/`, builds, and serves on port 3000.
- The completion condition is what makes the build-time-import safe: the Next
  build never runs against stale or missing marts.

## Images

### `Dockerfile.pipeline` (context = repo root)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .        # runtime dep is just duckdb
RUN mkdir -p data/raw /marts /data      # generate writes to data/raw
CMD python -m campaignflow run --db /data/campaignflow.duckdb \
 && python -m campaignflow export --db /data/campaignflow.duckdb --out /marts/marts.json
```

- Installs only the runtime dependency (`duckdb`); no pyspark/azure/dev extras, so
  the image stays lean and needs no JRE or Azurite for the default path.
- The exact directory `generate` writes its raw CSV into is confirmed during
  planning; the Dockerfile (or the pipeline itself) ensures it exists.

### `dashboard/Dockerfile` (context = `dashboard/`)

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["sh", "-c", "cp /marts/marts.json public/data/marts.json && npm run build && npm run start"]
```

- Dependencies are baked at image-build time (`npm ci`); only the ~20–30s
  `next build` runs at container start, once real marts are present.
- Healthcheck uses node itself (no curl/wget in the slim image):
  `node -e "require('http').get('http://localhost:3000',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"`.
- `next start` binds `0.0.0.0:3000` by default in the container, so the published
  port works.

### `.dockerignore` files

- Repo-root `.dockerignore`: exclude `.venv`, `.git`, `data/`, `*.duckdb`,
  `dashboard/node_modules`, `dashboard/.next`, and caches.
- `dashboard/.dockerignore`: exclude `node_modules` and `.next`.

The committed `dashboard/public/data/marts.json` stays as-is so the app still
builds standalone outside compose; at runtime the entrypoint overwrites it with
the fresh pipeline export.

## Compose file

`docker-compose.yml` (repo root):

```yaml
services:
  pipeline:
    build:
      context: .
      dockerfile: Dockerfile.pipeline
    volumes:
      - marts:/marts

  dashboard:
    build:
      context: ./dashboard
    depends_on:
      pipeline:
        condition: service_completed_successfully
    ports:
      - "3000:3000"
    volumes:
      - marts:/marts:ro
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"]
      interval: 10s
      timeout: 5s
      retries: 12          # ~2 min grace for the build+start
      start_period: 40s

volumes:
  marts:
```

## CI smoke test

A new `compose` job in `.github/workflows/ci.yml`, running alongside `test` and
`dashboard`:

1. `docker compose up -d --build`.
2. Poll until the `dashboard` container reports **healthy**; on timeout, dump
   `docker compose logs` and fail.
3. `curl -fsS localhost:3000` → assert HTTP 200 **and** grep the server-rendered
   footer for `seed 42`. This proves the *fresh* pipeline marts flowed
   build→render, not merely that a page served.
4. Always `docker compose down -v` (teardown, even on failure).

`ubuntu-latest` ships Docker + Compose v2, so no extra setup is required.

## Testing strategy (explicit TDD deviation)

Docker-compose is orchestration config; its behavior is only observable by running
the stack, so there is no isolated unit to Red/Green. The **CI smoke test is the
executable spec** for this extension — it fails today (no compose file exists) and
passes once the stack works. The existing `test` (pytest) and `dashboard` (Vitest)
jobs stay green and already prove the pipeline and app internals. This deviation
from unit-TDD is deliberate and recorded here so it is not silent.

## Files

- **New:** `docker-compose.yml`, `Dockerfile.pipeline`, `dashboard/Dockerfile`,
  `.dockerignore`, `dashboard/.dockerignore`.
- **Edited:** `.github/workflows/ci.yml` (add `compose` job), `README.md`
  (docker-compose quickstart + flip roadmap #4 to done), `HANDOFF.md` (mark #4
  shipped).

## Interview notes

Be able to explain: why the dashboard's build-time import forces the
`service_completed_successfully` ordering; why the pipeline is a run-to-completion
job rather than a long-running service; why Azurite and PySpark are deliberately
left out of the default compose path (keep the one-command demo lean and
dependency-light); and why the CI smoke test greps for `seed 42` rather than just
asserting HTTP 200 (proving data flow, not just liveness).
