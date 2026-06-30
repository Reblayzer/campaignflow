# CampaignFlow Dashboard — design

Status: approved 2026-06-30. Roadmap extension #3 (Next.js / TypeScript dashboard
over the gold marts).

## Goal

A small, public, runnable dashboard that visualises the gold marts: spend, CTR,
and cost-per-conversion by channel, plus spend over time. Built as a separate
static Next.js app so it deploys with no database or server at runtime.

## Key decisions

- **Build-time JSON export, not a live DB read.** Python owns the warehouse and
  publishes a versioned JSON contract (`marts.json`); the Next.js app only renders
  it. No DuckDB at runtime, no native binding, no API server. Deploys as a static
  site (Vercel/Pages). Mirrors a published BI extract downstream of gold.
- **Separate Node app under `dashboard/`.** Monorepo-style sibling to the Python
  package; its own `package.json`, tooling, and tests. The repo root stays Python.
- **Stack:** Next.js (App Router) + TypeScript, Recharts for charts, Tailwind CSS
  for layout, Vitest + Testing Library for tests.
- **Static, single page.** SSG only. No routing, filters, date pickers, live
  refresh, dark mode, or auth (YAGNI).

## Data flow

```
campaignflow run     -> campaignflow.duckdb
campaignflow export  -> dashboard/public/data/marts.json   (new CLI subcommand)
Next.js (SSG)        -> reads marts.json -> Recharts
```

The Node test suite reads a committed `dashboard/fixtures/marts.json`, so it runs
without Python or a warehouse.

## The export (`src/campaignflow/export.py`, new)

Reads the gold marts read-only and writes one `marts.json`. Reuses the existing
`report.py` aggregation logic (sum across months for the channel rollup).

Shape (the contract):

```json
{
  "generated_at": "2026-06-30T12:00:00Z",
  "seed": 42,
  "totals": {
    "spend_dkk": 0.0,
    "ctr_pct": 0.0,
    "cost_per_conversion": 0.0,
    "conversions": 0
  },
  "channels": [
    {
      "channel_group": "Paid",
      "channel_name": "Paid Search",
      "spend_dkk": 0.0,
      "clicks": 0,
      "conversions": 0,
      "ctr_pct": 0.0,
      "cost_per_conversion": 0.0
    }
  ],
  "monthly": [
    { "year_month": "2026-01", "spend_dkk": 0.0, "ctr_pct": 0.0, "cost_per_conversion": 0.0 }
  ]
}
```

- `totals` — blended KPIs across all channels and time. `ctr_pct` and
  `cost_per_conversion` are computed from summed numerators/denominators (not an
  average of ratios), so they reconcile with the fact.
- `channels[]` — per channel, aggregated over all time.
- `monthly[]` — per `year-month`, totals across channels, ordered ascending.

`generated_at` is passed in (callers stamp the time) so the export function stays
deterministic and testable; the CLI supplies the wall-clock value.

### CLI

`campaignflow export --db campaignflow.duckdb --out dashboard/public/data/marts.json`

Defaults: `--db campaignflow.duckdb`, `--out dashboard/public/data/marts.json`.

## Dashboard UI (single page, `dashboard/`)

- **KPI cards** — total spend (DKK), blended CTR %, blended cost-per-conversion,
  total conversions.
- **Three by-channel bar charts** — spend, CTR %, cost-per-conversion.
- **One monthly line chart** — spend over time, with a CTR / CPA metric toggle.

### Modules (each independently testable)

- `lib/marts.ts` — TypeScript types for the contract + a pure loader/validator
  that parses `marts.json` and throws on a malformed shape.
- `lib/format.ts` — pure formatters: DKK currency, percent, integer.
- `components/KpiCards.tsx` — totals row; props are the typed `totals`.
- `components/ChannelBarChart.tsx` — one reusable bar chart; props: data, value
  accessor, label, formatter.
- `components/MonthlyLineChart.tsx` — line chart with a metric toggle.
- `app/page.tsx` — reads the JSON at build time, composes the components.

## Testing

### Node (Vitest + Testing Library)

- `lib/format.ts` — unit tests for each formatter, including edge cases (zero,
  null/undefined, large numbers).
- `lib/marts.ts` — parse a fixture, assert typed access; assert it throws on a
  malformed object.
- Each component — render against `fixtures/marts.json`, assert labels/values are
  present and an empty-data case renders without crashing.

### Python (pytest, TDD)

- `export.py` — build a tiny warehouse (generate → bronze → silver → gold),
  export to a temp file, then assert:
  - the JSON has `totals`, `channels`, `monthly`, `generated_at`, `seed`;
  - summed `channels[].spend_dkk` reconciles to `totals.spend_dkk` (to the cent);
  - `monthly` is ordered ascending and covers the data's month range;
  - blended `ctr_pct` / `cost_per_conversion` match a direct fact query.
- CLI — `campaignflow export` writes the file to `--out`.

## CI

Extend `.github/workflows/ci.yml` with a second job (`dashboard`) that runs on the
Node app: `npm ci`, `tsc --noEmit`, `vitest run`, `next build`. It uses the
committed fixture, so it needs no Python, Java, or Azurite. The existing Python
`test` job is unchanged. Both jobs must be green to merge.

## Out of scope (YAGNI)

Routing, multiple pages, filters/date-pickers, live data refresh, dark mode, auth,
i18n, server-side rendering, and any runtime database access.
