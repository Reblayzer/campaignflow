# docker-compose Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the whole CampaignFlow stack run with one command — `docker compose up` builds the DuckDB warehouse, exports the gold marts, and serves the Next.js dashboard over them.

**Architecture:** Two services share one named volume. A run-to-completion `pipeline` service (Python) runs `campaignflow run` then `campaignflow export`, writing `marts.json` into the shared `marts` volume, then exits 0. A `dashboard` service (Node) starts only after the pipeline finishes successfully (`depends_on: service_completed_successfully`), copies the fresh marts into `public/data/`, runs `next build`, then `next start`. The completion-ordering is what satisfies the dashboard's build-time marts import. A CI smoke-test job brings the stack up and asserts it serves the fresh data.

**Tech Stack:** Docker, Docker Compose v2, `python:3.12-slim`, `node:22-slim`, GitHub Actions.

## Global Constraints

- Default compose path uses **in-process generation only** — no Azurite, no PySpark, no JRE. (Azurite landing zone stays a separate documented step.)
- Pipeline runtime dependency is **only `duckdb`** — install the package without the `dev`/`azure` extras.
- The dashboard's **static architecture is unchanged**: `page.tsx` still imports `public/data/marts.json` at build time. Compose orders services so that import target is fresh; no app code changes.
- The committed `dashboard/public/data/marts.json` **stays in the repo** (lets the app build standalone); the pipeline overwrites it at runtime inside the container.
- Dashboard must listen on `0.0.0.0:3000` inside the container so the published port is reachable from the host.
- CI smoke test must assert **both** that the page serves HTTP 200 **and** that the served static marts (`/data/marts.json`) contains `"seed": 42` (proves the marts contract was built and served, not just liveness). Note: do NOT grep the rendered HTML for `seed 42` — React SSR inserts a hydration comment between the `seed ` text node and the `{marts.seed}` expression (`seed <!-- -->42`), so that literal never appears. Assert against the served JSON instead. Freshness is proven separately: the `pipeline` service runs to completion as part of `up`.
- Conventional commits, scoped. Stage specific files only.

---

## File Structure

- `Dockerfile.pipeline` (repo root) — builds the Python pipeline image; runs `run` + `export`.
- `.dockerignore` (repo root) — trims the pipeline build context.
- `dashboard/Dockerfile` — builds the Node dashboard image; entrypoint copies marts, builds, starts.
- `dashboard/.dockerignore` — trims the dashboard build context.
- `docker-compose.yml` (repo root) — wires the two services, the `marts` volume, ordering, and healthcheck.
- `.github/workflows/ci.yml` — add a `compose` smoke-test job.
- `README.md` — docker-compose quickstart + flip roadmap #4 to done.
- `HANDOFF.md` — mark #4 shipped.

---

### Task 1: Pipeline image + root .dockerignore

**Files:**
- Create: `Dockerfile.pipeline`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: `pyproject.toml`, `src/campaignflow/` (existing). `python -m campaignflow run` writes `campaignflow.duckdb` in WORKDIR and `data/raw/` (auto-created by `generate_raw`); `python -m campaignflow export --out <path>` reads that db and writes marts JSON (parent dir auto-created by `export_marts`).
- Produces: an image whose default `CMD` writes `/marts/marts.json` — a valid marts contract with `"seed": 42` — then exits 0. Consumed by Task 3 (compose).

- [ ] **Step 1: Write the root `.dockerignore`**

Create `.dockerignore`:

```
.git
.venv
venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
*.egg-info
build
dist
data
*.duckdb
dashboard/node_modules
dashboard/.next
docs
infra
```

- [ ] **Step 2: Write `Dockerfile.pipeline`**

Create `Dockerfile.pipeline`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# run builds campaignflow.duckdb (+ data/raw, auto-created);
# export writes marts.json into the shared /marts volume (parent auto-created).
CMD python -m campaignflow run && python -m campaignflow export --out /marts/marts.json
```

- [ ] **Step 3: Build the image (verify it builds)**

Run: `docker build -f Dockerfile.pipeline -t cf-pipeline .`
Expected: build succeeds, ending with a line like `naming to docker.io/library/cf-pipeline`.

- [ ] **Step 4: Run the container and verify it produces valid marts**

Run:

```bash
rm -rf /tmp/cf-marts && mkdir -p /tmp/cf-marts
docker run --rm -v /tmp/cf-marts:/marts cf-pipeline
test -f /tmp/cf-marts/marts.json && grep -q '"seed": 42' /tmp/cf-marts/marts.json && echo "MARTS OK"
```

Expected: the run prints the `campaignflow run complete:` summary and `exported marts to /marts/marts.json`, and the final line prints `MARTS OK`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.pipeline .dockerignore
git commit -m "feat(docker): pipeline image that builds and exports the marts"
```

---

### Task 2: Dashboard image + dashboard/.dockerignore

**Files:**
- Create: `dashboard/Dockerfile`
- Create: `dashboard/.dockerignore`

**Interfaces:**
- Consumes: `dashboard/package.json`, `dashboard/package-lock.json`, the dashboard source (existing). Expects `/marts/marts.json` to exist at container start (provided by Task 1's service via the shared volume in Task 3).
- Produces: an image whose entrypoint copies `/marts/marts.json` → `public/data/marts.json`, runs `next build`, then `next start -H 0.0.0.0 -p 3000`. Consumed by Task 3 (compose).

- [ ] **Step 1: Write `dashboard/.dockerignore`**

Create `dashboard/.dockerignore`:

```
node_modules
.next
```

- [ ] **Step 2: Write `dashboard/Dockerfile`**

Create `dashboard/Dockerfile`:

```dockerfile
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# At start: overwrite the committed marts with the fresh pipeline export,
# then build and serve. -H 0.0.0.0 so the published port is reachable.
CMD ["sh", "-c", "cp /marts/marts.json public/data/marts.json && npm run build && npm run start -- -H 0.0.0.0 -p 3000"]
```

- [ ] **Step 3: Build the image (verify it builds)**

Run: `docker build -t cf-dashboard dashboard/`
Expected: build succeeds (`npm ci` installs deps, image tagged `cf-dashboard`). No `next build` runs here — that happens at container start — so a successful build only proves deps install and the context copies cleanly.

- [ ] **Step 4: Commit**

```bash
git add dashboard/Dockerfile dashboard/.dockerignore
git commit -m "feat(docker): dashboard image that builds and serves over fresh marts"
```

---

### Task 3: docker-compose.yml wiring both services

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: `cf-pipeline` (Task 1) and `cf-dashboard` (Task 2) images, built from their Dockerfiles.
- Produces: a working stack — `docker compose up` serves the dashboard on host `:3000` with the fresh marts. Consumed by Task 4 (CI encodes the same up/assert/down sequence).

- [ ] **Step 1: Write `docker-compose.yml`**

Create `docker-compose.yml`:

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
      retries: 12
      start_period: 120s      # headroom: the container runs `next build` before it serves

volumes:
  marts:
```

- [ ] **Step 2: Validate the compose file parses**

Run: `docker compose config`
Expected: prints the normalized config with both `pipeline` and `dashboard` services and the `marts` volume; exits 0. No error.

- [ ] **Step 3: Bring the stack up and assert it serves fresh marts**

Use `--wait` so Compose blocks until the pipeline exits 0 and the dashboard is healthy (no arbitrary sleep loop). Then assert the served static marts contain `"seed": 42` and the page returns 200:

```bash
docker compose up -d --build --wait --wait-timeout 480
curl -fsS http://localhost:3000/data/marts.json -o /tmp/cf-marts.json
curl -fsS http://localhost:3000 -o /dev/null
grep -q '"seed": 42' /tmp/cf-marts.json && echo "STACK OK"
```

Expected: `docker compose up --wait` returns once the stack is ready (up to ~8 min for the build); the served `/data/marts.json` contains `"seed": 42`; the page returns 200; the final line prints `STACK OK`. If it fails, inspect with `docker compose logs` (both `pipeline` and `dashboard`).

- [ ] **Step 4: Tear the stack down**

Run: `docker compose down -v`
Expected: both containers and the `marts` volume are removed; exits 0.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): compose the pipeline and dashboard into a one-command stack"
```

---

### Task 4: CI smoke-test job

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `docker-compose.yml` (Task 3) and both Dockerfiles.
- Produces: a `compose` CI job that builds the stack, waits for it (`--wait`), asserts the page returns 200 and the served `/data/marts.json` contains `"seed": 42`, and always tears down. Runs alongside the existing `test` and `dashboard` jobs.

- [ ] **Step 1: Add the `compose` job**

In `.github/workflows/ci.yml`, add a new job under `jobs:` (a sibling of `test` and `dashboard`), at the end of the file:

```yaml
  compose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and start the stack
        run: docker compose up -d --build --wait --wait-timeout 480
      - name: Assert the stack serves the marts
        run: |
          if ! curl -fsS http://localhost:3000/data/marts.json -o marts.json; then
            echo "dashboard did not serve /data/marts.json" >&2
            docker compose logs
            exit 1
          fi
          if ! curl -fsS http://localhost:3000 -o /dev/null; then
            echo "dashboard page did not return 200" >&2
            docker compose logs
            exit 1
          fi
          if ! grep -q '"seed": 42' marts.json; then
            echo "served marts did not contain the expected contract (\"seed\": 42)" >&2
            cat marts.json >&2
            exit 1
          fi
          echo "stack served the marts"
      - name: Dump logs on failure
        if: failure()
        run: docker compose logs
      - name: Tear down
        if: always()
        run: docker compose down -v
```

Note: `docker compose up --wait` blocks until the `pipeline` service exits 0 and the `dashboard` service is healthy (per its healthcheck), so no manual poll loop is needed. `--wait-timeout 480` bounds the wait at 8 minutes to cover a cold `next build` on a CI runner.

- [ ] **Step 2: Validate the workflow YAML is well-formed**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"`
Expected: prints `YAML OK` (no parse error).

- [ ] **Step 3: Verify the job locally (same sequence CI runs)**

Run:

```bash
docker compose up -d --build --wait --wait-timeout 480
curl -fsS http://localhost:3000/data/marts.json -o /tmp/cf-marts.json
curl -fsS http://localhost:3000 -o /dev/null
grep -q '"seed": 42' /tmp/cf-marts.json && echo "CI SEQUENCE OK"
docker compose down -v
```

Expected: prints `CI SEQUENCE OK`, then the teardown removes the containers and volume.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: smoke-test the docker-compose stack end to end"
```

---

### Task 5: Documentation

**Files:**
- Modify: `README.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: the shipped compose stack (Tasks 1–4).
- Produces: user-facing docs (README quickstart + roadmap) and the updated handoff. No code.

- [ ] **Step 1: Add a docker-compose section to the README**

In `README.md`, add this section immediately before the `## Roadmap` heading (the
outer four-backtick fence below is only to show the nested code block — copy the
inner content verbatim):

````markdown
## One command with docker compose

The whole stack runs with a single command — no local Python or Node needed:

```bash
docker compose up --build      # builds the warehouse, exports marts, serves the app
# open http://localhost:3000
docker compose down -v         # stop and clean up
```

The `pipeline` service builds the DuckDB warehouse and exports the gold marts into
a shared volume, then exits; the `dashboard` service waits for it to finish, then
builds and serves the Next.js app over the fresh marts. Azurite (the blob landing
zone) is not part of this default stack — see *Blob landing zone* above to exercise
that path.
````

- [ ] **Step 2: Flip roadmap item #4 to done**

In `README.md`, under `## Roadmap`, move item 4 from "Planned" to "Shipped" and mark it done. Change the planned block so it reads:

```markdown
4. ~~**docker-compose**~~ — done (see *One command with docker compose* above).
```

Remove the now-empty "Planned extensions:" block if item 4 was its only entry.

- [ ] **Step 3: Verify README links/sections are consistent**

Run: `grep -n "docker compose\|Roadmap\|docker-compose" README.md`
Expected: shows the new section heading, the `docker compose up --build` command, and the struck-through roadmap item 4.

- [ ] **Step 4: Update HANDOFF.md**

In `HANDOFF.md`, update the status line and ladder to reflect #4 shipped:

- Change the `## Status:` heading to: `## Status: core + four extensions shipped; docker-compose is the last ladder item`
- Add a bullet after the Extension #3 bullet:

```markdown
- **Extension #4 shipped:** `docker compose up` runs the whole stack — a `pipeline`
  service builds the warehouse and exports the marts into a shared volume, then a
  `dashboard` service builds and serves the Next.js app over them. CI gained a
  `compose` smoke-test job (page 200 + served marts contain `"seed": 42`). Spec/plan:
  `docs/superpowers/{specs,plans}/2026-07-01-docker-compose*.md`.
```

- In the "Next steps (extension ladder...)" list, change item 4 to: `4. ~~docker-compose~~ — shipped.`
- Replace the "On resume — build docker-compose (#4)" section with a short note that the ladder is complete and future work is open-ended (pick from the README roadmap's "later" items).

- [ ] **Step 5: Commit**

```bash
git add README.md HANDOFF.md
git commit -m "docs: document the docker-compose stack and mark extension #4 shipped"
```

---

### Task 6: Open the PR

**Files:** none (git/PR only).

**Interfaces:**
- Consumes: all commits from Tasks 1–5 on `feat/docker-compose`.
- Produces: an open PR against `main` with all three CI jobs (`test`, `dashboard`, `compose`) green.

- [ ] **Step 1: Push the branch**

Run: `git push -u origin feat/docker-compose`
Expected: branch pushed; prints the PR-create hint URL.

- [ ] **Step 2: Open the PR**

Run:

```bash
gh pr create --base main --head feat/docker-compose \
  --title "feat(docker): one-command docker compose stack" \
  --body "$(cat <<'BODY'
## Summary
Extension #4 of the CampaignFlow ladder. `docker compose up` builds the DuckDB
warehouse, exports the gold marts, and serves the Next.js dashboard over them —
one command, no local Python or Node.

- `pipeline` service (python:3.12-slim): runs `campaignflow run` + `export`,
  writes `marts.json` into a shared volume, exits 0.
- `dashboard` service (node:22-slim): waits via `service_completed_successfully`,
  copies the fresh marts, runs `next build`, then `next start`.
- The completion-ordering satisfies the dashboard's build-time marts import; no
  app code changed.
- Azurite/PySpark deliberately left out of the default stack to keep the
  one-command demo lean.

## Test plan
- New `compose` CI job: `docker compose up -d --build --wait`, then assert the
  page returns 200 **and** the served static marts (`/data/marts.json`) contain
  `"seed": 42` (the pipeline running to completion as part of `up` proves
  freshness), then `docker compose down -v`.
- Existing `test` (pytest) and `dashboard` (Vitest + build) jobs stay green.

Spec: `docs/superpowers/specs/2026-07-01-docker-compose-design.md`
Plan: `docs/superpowers/plans/2026-07-01-docker-compose.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

Expected: prints the new PR URL.

- [ ] **Step 3: Confirm CI is green**

Run: `gh pr checks --watch`
Expected: all three jobs — `test`, `dashboard`, `compose` — report `pass`.

---

## Notes on the TDD deviation

Docker-compose is orchestration config; its behavior is only observable by running
the stack, so there is no isolated unit to Red/Green. Each task above still follows
a verify-it-fails-then-passes rhythm using real Docker commands (build fails before
the Dockerfile exists; the stack does not serve before the compose file exists),
and the **CI `compose` job is the executable spec** — it fails today (no compose
file) and passes once the stack works. The existing pytest and Vitest suites keep
proving the pipeline and app internals. This deviation is deliberate and recorded
here and in the spec.
