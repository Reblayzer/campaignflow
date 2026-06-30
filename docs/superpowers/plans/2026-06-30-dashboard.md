# CampaignFlow Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A static Next.js dashboard over the gold marts (spend / CTR / cost-per-conversion by channel and over time), fed by a build-time JSON export from the Python warehouse.

**Architecture:** Python gains a `campaignflow export` command that writes `dashboard/public/data/marts.json` from the gold marts (read-only). A separate static Next.js app under `dashboard/` reads that JSON at build time and renders KPI cards + Recharts charts. No database, native binding, or server at runtime.

**Tech Stack:** Python 3.12 + DuckDB (export); Next.js (App Router) + TypeScript + Recharts + Tailwind CSS + Vitest + Testing Library (dashboard).

## Global Constraints

- Python: ruff clean (`select = E, F, I, UP, B`, line-length 100, ignore E501), TDD with pytest, `pythonpath = src`.
- Money/ratio JSON values are floats (cast DuckDB `decimal`/`bigint` via `cast(... as double)`); count values are integers.
- `ctr_pct` and `cost_per_conversion` are computed from **summed** numerators/denominators, never an average of ratios.
- `export_marts` takes `generated_at` as a parameter (no `datetime.now()` inside it) so it stays deterministic and testable; the CLI supplies the wall-clock value.
- Node app lives entirely under `dashboard/`; the repo root stays Python. Import alias `@/*`.
- Components are presentational and take typed props; all tests run against a committed `dashboard/fixtures/marts.json` (no Python needed).
- Conventional commits, stage specific files (never `git add .`), one logical change per commit.
- Contract types must match exactly across Python export and TS `lib/marts.ts`.

---

### Task 1: Python `build_marts` — the marts contract

**Files:**
- Create: `src/campaignflow/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `campaignflow.db.connect`, `campaignflow.bronze.load_raw`, `campaignflow.silver.build_silver`, `campaignflow.gold.build_gold`, `campaignflow.generate.generate_raw`.
- Produces: `build_marts(con: duckdb.DuckDBPyConnection, generated_at: str, seed: int) -> dict` returning keys `generated_at, seed, totals, channels, monthly`. `totals` = `{spend_dkk: float, ctr_pct: float, cost_per_conversion: float, conversions: int}`. `channels[]` items = `{channel_group, channel_name, spend_dkk, clicks, conversions, ctr_pct, cost_per_conversion}`. `monthly[]` items = `{year_month, spend_dkk, ctr_pct, cost_per_conversion}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export.py
from campaignflow.bronze import load_raw
from campaignflow.db import connect
from campaignflow.export import build_marts
from campaignflow.generate import generate_raw
from campaignflow.gold import build_gold
from campaignflow.silver import build_silver


def _seed_warehouse(tmp_path):
    con = connect(":memory:")
    load_raw(con, generate_raw(rows=600, seed=11, out_dir=tmp_path))
    build_silver(con)
    build_gold(con)
    return con


def test_build_marts_shape_and_reconciliation(tmp_path):
    con = _seed_warehouse(tmp_path)
    marts = build_marts(con, generated_at="2026-06-30T12:00:00Z", seed=11)

    assert set(marts) == {"generated_at", "seed", "totals", "channels", "monthly"}
    assert marts["generated_at"] == "2026-06-30T12:00:00Z"
    assert marts["seed"] == 11

    # channel spend reconciles to totals (to the cent)
    channel_spend = round(sum(c["spend_dkk"] for c in marts["channels"]), 2)
    assert channel_spend == marts["totals"]["spend_dkk"]

    # monthly is ascending and non-empty
    months = [m["year_month"] for m in marts["monthly"]]
    assert months == sorted(months) and len(months) > 0

    # JSON-serialisable primitives only (no Decimal)
    assert isinstance(marts["totals"]["spend_dkk"], float)
    assert isinstance(marts["totals"]["conversions"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'campaignflow.export'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/campaignflow/export.py
import duckdb

_TOTALS = """
select
    cast(round(sum(spend_dkk), 2) as double)                                  as spend_dkk,
    cast(round(100.0 * sum(clicks) / nullif(sum(impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(spend_dkk) / nullif(sum(conversions), 0), 2) as double)     as cost_per_conversion,
    cast(sum(conversions) as bigint)                                          as conversions
from gold.fact_campaign_performance
"""

_CHANNELS = """
select
    ch.channel_group,
    ch.channel_name,
    cast(round(sum(f.spend_dkk), 2) as double)                                    as spend_dkk,
    cast(sum(f.clicks) as bigint)                                                 as clicks,
    cast(sum(f.conversions) as bigint)                                            as conversions,
    cast(round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2) as double)     as cost_per_conversion
from gold.fact_campaign_performance f
join gold.dim_channel ch on f.channel_key = ch.channel_key
group by 1, 2
order by ch.channel_group, ch.channel_name
"""

_MONTHLY = """
select
    printf('%04d-%02d', d.year, d.month)                                          as year_month,
    cast(round(sum(f.spend_dkk), 2) as double)                                    as spend_dkk,
    cast(round(100.0 * sum(f.clicks) / nullif(sum(f.impressions), 0), 2) as double) as ctr_pct,
    cast(round(sum(f.spend_dkk) / nullif(sum(f.conversions), 0), 2) as double)     as cost_per_conversion
from gold.fact_campaign_performance f
join gold.dim_date d on f.date_key = d.date_key
group by 1
order by 1
"""


def build_marts(con: duckdb.DuckDBPyConnection, generated_at: str, seed: int) -> dict:
    """Read the gold marts into the dashboard contract (JSON-serialisable dict)."""
    t = con.execute(_TOTALS).fetchone()
    totals = {
        "spend_dkk": t[0],
        "ctr_pct": t[1],
        "cost_per_conversion": t[2],
        "conversions": t[3],
    }
    channels = [
        {
            "channel_group": r[0],
            "channel_name": r[1],
            "spend_dkk": r[2],
            "clicks": r[3],
            "conversions": r[4],
            "ctr_pct": r[5],
            "cost_per_conversion": r[6],
        }
        for r in con.execute(_CHANNELS).fetchall()
    ]
    monthly = [
        {"year_month": r[0], "spend_dkk": r[1], "ctr_pct": r[2], "cost_per_conversion": r[3]}
        for r in con.execute(_MONTHLY).fetchall()
    ]
    return {
        "generated_at": generated_at,
        "seed": seed,
        "totals": totals,
        "channels": channels,
        "monthly": monthly,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/campaignflow/export.py tests/test_export.py
git commit -m "feat(export): build gold-marts dashboard contract from DuckDB"
```

---

### Task 2: `export_marts` writer + reconciliation against the fact

**Files:**
- Modify: `src/campaignflow/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `build_marts` (Task 1).
- Produces: `export_marts(db_path: str, out_path: str | Path, generated_at: str, seed: int = SEED) -> dict` — writes `out_path` (creating parents) as indented JSON and returns the marts dict.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_export.py
import json
from pathlib import Path

from campaignflow.export import export_marts
from campaignflow.pipeline import run


def test_export_marts_writes_file_and_matches_fact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "cf.duckdb")
    run(db_path=db, rows=800, seed=21)

    out = tmp_path / "marts.json"
    marts = export_marts(db, out, generated_at="2026-06-30T00:00:00Z", seed=21)

    on_disk = json.loads(Path(out).read_text())
    assert on_disk == marts
    assert on_disk["totals"]["conversions"] > 0
    assert len(on_disk["channels"]) == 6  # six channels in config
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export.py::test_export_marts_writes_file_and_matches_fact -v`
Expected: FAIL with `ImportError: cannot import name 'export_marts'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/campaignflow/export.py
import json
from pathlib import Path

from campaignflow.config import SEED


def export_marts(
    db_path: str, out_path: str | Path, generated_at: str, seed: int = SEED
) -> dict:
    """Export the gold marts to a JSON file the dashboard reads at build time."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        marts = build_marts(con, generated_at=generated_at, seed=seed)
    finally:
        con.close()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(marts, indent=2) + "\n")
    return marts
```

Move the `import json` / `from pathlib import Path` / `from campaignflow.config import SEED` to the top of the file with the existing `import duckdb` (ruff `I` will enforce ordering: stdlib `json`, then `pathlib`; third-party `duckdb`; first-party `campaignflow.config`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run ruff**

Run: `ruff check src/campaignflow/export.py tests/test_export.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/campaignflow/export.py tests/test_export.py
git commit -m "feat(export): write marts.json and reconcile to the fact"
```

---

### Task 3: `campaignflow export` CLI subcommand

**Files:**
- Modify: `src/campaignflow/cli.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `export_marts` (Task 2).
- Produces: CLI `export` subcommand with `--db` (default `campaignflow.duckdb`) and `--out` (default `dashboard/public/data/marts.json`); parser sets `args.db`, `args.out`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_smoke.py
def test_export_parser_has_db_and_out_defaults():
    args = build_parser().parse_args(["export"])
    assert args.db == "campaignflow.duckdb"
    assert args.out == "dashboard/public/data/marts.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py::test_export_parser_has_db_and_out_defaults -v`
Expected: FAIL — `argument command: invalid choice: 'export'`

- [ ] **Step 3: Write minimal implementation**

In `build_parser()`, after the `report_p` block:

```python
    export_p = sub.add_parser("export", help="Export gold marts to JSON for the dashboard.")
    export_p.add_argument("--db", default="campaignflow.duckdb", help="DuckDB file path.")
    export_p.add_argument(
        "--out",
        default="dashboard/public/data/marts.json",
        help="Output JSON path for the dashboard.",
    )
```

In `main()`, before the final `parser.print_help()`:

```python
    if args.command == "export":
        from datetime import datetime, timezone

        from campaignflow.export import export_marts

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        export_marts(db_path=args.db, out_path=args.out, generated_at=generated_at)
        print(f"exported marts to {args.out}")
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Run full Python suite + ruff**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/campaignflow/cli.py tests/test_smoke.py
git commit -m "feat(cli): add export subcommand for the dashboard marts"
```

---

### Task 4: Generate the marts fixture + scaffold the Next.js app

**Files:**
- Create: `dashboard/` (via create-next-app)
- Create: `dashboard/fixtures/marts.json`
- Modify: `dashboard/package.json` (add deps + scripts)
- Create: `dashboard/.gitignore` already provided by create-next-app

**Interfaces:**
- Produces: a runnable Next.js app under `dashboard/` with Recharts + Vitest installed; a committed `dashboard/fixtures/marts.json` test fixture matching the contract.

- [ ] **Step 1: Scaffold the app (run from repo root)**

```bash
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm --no-turbopack
```

- [ ] **Step 2: Install dashboard dependencies**

```bash
cd dashboard
npm install recharts
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
cd ..
```

- [ ] **Step 3: Generate the fixture from a real run**

```bash
python -m campaignflow run --db /tmp/cf_fixture.duckdb --rows 800 --seed 21
python -m campaignflow export --db /tmp/cf_fixture.duckdb --out dashboard/fixtures/marts.json
```

- [ ] **Step 4: Add Vitest config**

Create `dashboard/vitest.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

Create `dashboard/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Add scripts to `dashboard/package.json`**

In the `"scripts"` block add:

```json
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
```

- [ ] **Step 6: Verify the toolchain builds**

Run:
```bash
cd dashboard && npm run typecheck && npm run build && cd ..
```
Expected: type check passes and `next build` succeeds (default starter page).

- [ ] **Step 7: Commit**

```bash
git add dashboard
git commit -m "chore(dashboard): scaffold Next.js app with Recharts and Vitest"
```

---

### Task 5: `lib/format.ts` formatters

**Files:**
- Create: `dashboard/lib/format.ts`
- Test: `dashboard/lib/format.test.ts`

**Interfaces:**
- Produces: `formatDkk(v)`, `formatPercent(v)`, `formatInt(v)` — each `(value: number | null | undefined) => string`, returning `"—"` for non-finite/nullish input.

- [ ] **Step 1: Write the failing test**

```ts
// dashboard/lib/format.test.ts
import { describe, expect, it } from "vitest";
import { formatDkk, formatInt, formatPercent } from "./format";

describe("formatters", () => {
  it("formats DKK with no decimals", () => {
    expect(formatDkk(1234.5)).toMatch(/1.?235/); // locale-grouped, rounded
    expect(formatDkk(1234.5)).toMatch(/kr/i);
  });
  it("formats percent to two decimals", () => {
    expect(formatPercent(2.5)).toBe("2.50%");
  });
  it("formats integers with grouping", () => {
    expect(formatInt(1234567)).toBe("1,234,567");
  });
  it("returns em dash for nullish/non-finite", () => {
    expect(formatDkk(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
    expect(formatInt(NaN)).toBe("—");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run lib/format.test.ts`
Expected: FAIL — cannot find module `./format`

- [ ] **Step 3: Write minimal implementation**

```ts
// dashboard/lib/format.ts
function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || !Number.isFinite(value);
}

export function formatDkk(value: number | null | undefined): string {
  if (isMissing(value)) return "—";
  return new Intl.NumberFormat("da-DK", {
    style: "currency",
    currency: "DKK",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (isMissing(value)) return "—";
  return `${value.toFixed(2)}%`;
}

export function formatInt(value: number | null | undefined): string {
  if (isMissing(value)) return "—";
  return new Intl.NumberFormat("en-US").format(value);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard && npx vitest run lib/format.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib/format.ts dashboard/lib/format.test.ts
git commit -m "feat(dashboard): pure DKK/percent/int formatters"
```

---

### Task 6: `lib/marts.ts` contract types + parser

**Files:**
- Create: `dashboard/lib/marts.ts`
- Test: `dashboard/lib/marts.test.ts`

**Interfaces:**
- Consumes: `dashboard/fixtures/marts.json` (Task 4).
- Produces: interfaces `Totals`, `ChannelRow`, `MonthlyRow`, `Marts`; `parseMarts(raw: unknown): Marts` throwing `Error` on a malformed shape.

- [ ] **Step 1: Write the failing test**

```ts
// dashboard/lib/marts.test.ts
import { describe, expect, it } from "vitest";
import fixture from "../fixtures/marts.json";
import { parseMarts } from "./marts";

describe("parseMarts", () => {
  it("accepts the committed fixture and exposes typed fields", () => {
    const marts = parseMarts(fixture);
    expect(marts.channels.length).toBe(6);
    expect(typeof marts.totals.spend_dkk).toBe("number");
    expect(marts.monthly[0].year_month).toMatch(/^\d{4}-\d{2}$/);
  });
  it("throws on a malformed shape", () => {
    expect(() => parseMarts({ totals: {} })).toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run lib/marts.test.ts`
Expected: FAIL — cannot find module `./marts`

- [ ] **Step 3: Write minimal implementation**

```ts
// dashboard/lib/marts.ts
export interface Totals {
  spend_dkk: number;
  ctr_pct: number;
  cost_per_conversion: number;
  conversions: number;
}

export interface ChannelRow {
  channel_group: string;
  channel_name: string;
  spend_dkk: number;
  clicks: number;
  conversions: number;
  ctr_pct: number;
  cost_per_conversion: number;
}

export interface MonthlyRow {
  year_month: string;
  spend_dkk: number;
  ctr_pct: number;
  cost_per_conversion: number;
}

export interface Marts {
  generated_at: string;
  seed: number;
  totals: Totals;
  channels: ChannelRow[];
  monthly: MonthlyRow[];
}

export function parseMarts(raw: unknown): Marts {
  const m = raw as Marts;
  const ok =
    !!m &&
    typeof m === "object" &&
    !!m.totals &&
    typeof m.totals.spend_dkk === "number" &&
    Array.isArray(m.channels) &&
    Array.isArray(m.monthly);
  if (!ok) {
    throw new Error("Invalid marts.json shape");
  }
  return m;
}
```

- [ ] **Step 4: Verify `resolveJsonModule` is enabled**

Confirm `dashboard/tsconfig.json` has `"resolveJsonModule": true` (create-next-app sets it). If missing, add it under `compilerOptions`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd dashboard && npx vitest run lib/marts.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/marts.ts dashboard/lib/marts.test.ts
git commit -m "feat(dashboard): marts contract types and parser"
```

---

### Task 7: `KpiCards` component

**Files:**
- Create: `dashboard/components/KpiCards.tsx`
- Test: `dashboard/components/KpiCards.test.tsx`

**Interfaces:**
- Consumes: `Totals` (Task 6), formatters (Task 5).
- Produces: `KpiCards({ totals }: { totals: Totals })`.

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/components/KpiCards.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiCards } from "./KpiCards";

const totals = { spend_dkk: 1000, ctr_pct: 2.5, cost_per_conversion: 12.34, conversions: 80 };

describe("KpiCards", () => {
  it("renders the four KPI labels and values", () => {
    render(<KpiCards totals={totals} />);
    expect(screen.getByText(/total spend/i)).toBeInTheDocument();
    expect(screen.getByText("2.50%")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run components/KpiCards.test.tsx`
Expected: FAIL — cannot find module `./KpiCards`

- [ ] **Step 3: Write minimal implementation**

```tsx
// dashboard/components/KpiCards.tsx
import type { Totals } from "@/lib/marts";
import { formatDkk, formatInt, formatPercent } from "@/lib/format";

export function KpiCards({ totals }: { totals: Totals }) {
  const cards = [
    { label: "Total spend", value: formatDkk(totals.spend_dkk) },
    { label: "Blended CTR", value: formatPercent(totals.ctr_pct) },
    { label: "Cost / conversion", value: formatDkk(totals.cost_per_conversion) },
    { label: "Conversions", value: formatInt(totals.conversions) },
  ];
  return (
    <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">{c.label}</p>
          <p className="mt-1 text-2xl font-semibold">{c.value}</p>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard && npx vitest run components/KpiCards.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/KpiCards.tsx dashboard/components/KpiCards.test.tsx
git commit -m "feat(dashboard): KPI cards for blended totals"
```

---

### Task 8: `ChannelBarChart` component

**Files:**
- Create: `dashboard/components/ChannelBarChart.tsx`
- Test: `dashboard/components/ChannelBarChart.test.tsx`

**Interfaces:**
- Consumes: `ChannelRow` (Task 6).
- Produces: `ChannelBarChart({ data, dataKey, title }: { data: ChannelRow[]; dataKey: keyof ChannelRow; title: string })`.

> Recharts' `ResponsiveContainer` renders nothing at zero size in jsdom. The component must render a heading and an accessible list of the values alongside the chart, so tests assert on those, not on SVG geometry.

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/components/ChannelBarChart.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChannelRow } from "@/lib/marts";
import { ChannelBarChart } from "./ChannelBarChart";

const data: ChannelRow[] = [
  { channel_group: "Paid", channel_name: "Paid Search", spend_dkk: 500, clicks: 10, conversions: 5, ctr_pct: 2.5, cost_per_conversion: 100 },
  { channel_group: "Owned", channel_name: "Email", spend_dkk: 200, clicks: 4, conversions: 2, ctr_pct: 1.0, cost_per_conversion: 100 },
];

describe("ChannelBarChart", () => {
  it("renders the title and one row per channel", () => {
    render(<ChannelBarChart data={data} dataKey="spend_dkk" title="Spend by channel" />);
    expect(screen.getByRole("heading", { name: /spend by channel/i })).toBeInTheDocument();
    expect(screen.getByText("Paid Search")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
  });

  it("renders an empty state with no data", () => {
    render(<ChannelBarChart data={[]} dataKey="spend_dkk" title="Spend by channel" />);
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run components/ChannelBarChart.test.tsx`
Expected: FAIL — cannot find module `./ChannelBarChart`

- [ ] **Step 3: Write minimal implementation**

```tsx
// dashboard/components/ChannelBarChart.tsx
"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChannelRow } from "@/lib/marts";

export function ChannelBarChart({
  data,
  dataKey,
  title,
}: {
  data: ChannelRow[];
  dataKey: keyof ChannelRow;
  title: string;
}) {
  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <h2 className="mb-2 text-lg font-semibold">{title}</h2>
      {data.length === 0 ? (
        <p className="text-gray-500">No data</p>
      ) : (
        <>
          <ul className="sr-only">
            {data.map((d) => (
              <li key={d.channel_name}>
                {d.channel_name}: {String(d[dataKey])}
              </li>
            ))}
          </ul>
          <div className="h-64" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="channel_name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={dataKey as string} fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}
```

> The `sr-only` list is keyed and labelled per channel so the test (and screen readers) can read channel names without the SVG. `channel_name` appears in both the `sr-only` list and the (aria-hidden) axis; `getByText` matches the visible-to-AOM `sr-only` entry.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard && npx vitest run components/ChannelBarChart.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/ChannelBarChart.tsx dashboard/components/ChannelBarChart.test.tsx
git commit -m "feat(dashboard): reusable by-channel bar chart"
```

---

### Task 9: `MonthlyLineChart` component with metric toggle

**Files:**
- Create: `dashboard/components/MonthlyLineChart.tsx`
- Test: `dashboard/components/MonthlyLineChart.test.tsx`

**Interfaces:**
- Consumes: `MonthlyRow` (Task 6).
- Produces: `MonthlyLineChart({ data }: { data: MonthlyRow[] })` with buttons to switch metric between `spend_dkk`, `ctr_pct`, `cost_per_conversion`.

- [ ] **Step 1: Write the failing test**

```tsx
// dashboard/components/MonthlyLineChart.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { MonthlyRow } from "@/lib/marts";
import { MonthlyLineChart } from "./MonthlyLineChart";

const data: MonthlyRow[] = [
  { year_month: "2026-01", spend_dkk: 100, ctr_pct: 2.0, cost_per_conversion: 50 },
  { year_month: "2026-02", spend_dkk: 200, ctr_pct: 2.5, cost_per_conversion: 40 },
];

describe("MonthlyLineChart", () => {
  it("defaults to the spend metric and toggles to CTR", async () => {
    render(<MonthlyLineChart data={data} />);
    const spendButton = screen.getByRole("button", { name: /spend/i });
    expect(spendButton).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: /ctr/i }));
    expect(screen.getByRole("button", { name: /ctr/i })).toHaveAttribute("aria-pressed", "true");
    expect(spendButton).toHaveAttribute("aria-pressed", "false");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && npx vitest run components/MonthlyLineChart.test.tsx`
Expected: FAIL — cannot find module `./MonthlyLineChart`

- [ ] **Step 3: Write minimal implementation**

```tsx
// dashboard/components/MonthlyLineChart.tsx
"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthlyRow } from "@/lib/marts";

const METRICS: { key: keyof MonthlyRow; label: string }[] = [
  { key: "spend_dkk", label: "Spend" },
  { key: "ctr_pct", label: "CTR" },
  { key: "cost_per_conversion", label: "CPA" },
];

export function MonthlyLineChart({ data }: { data: MonthlyRow[] }) {
  const [metric, setMetric] = useState<keyof MonthlyRow>("spend_dkk");
  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Over time</h2>
        <div className="flex gap-1">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              aria-pressed={metric === m.key}
              onClick={() => setMetric(m.key)}
              className={`rounded px-2 py-1 text-sm ${
                metric === m.key ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="h-72" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year_month" tick={{ fontSize: 11 }} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey={metric as string} stroke="#2563eb" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard && npx vitest run components/MonthlyLineChart.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/components/MonthlyLineChart.tsx dashboard/components/MonthlyLineChart.test.tsx
git commit -m "feat(dashboard): monthly line chart with metric toggle"
```

---

### Task 10: Compose the page

**Files:**
- Modify: `dashboard/app/page.tsx`
- Modify: `dashboard/app/layout.tsx` (title/metadata only)
- Create: `dashboard/public/data/marts.json` (copy of the fixture so the app builds before a Python run)

**Interfaces:**
- Consumes: `parseMarts` (6), `KpiCards` (7), `ChannelBarChart` (8), `MonthlyLineChart` (9).
- Produces: the rendered dashboard page.

- [ ] **Step 1: Seed the build-time data file**

```bash
mkdir -p dashboard/public/data
cp dashboard/fixtures/marts.json dashboard/public/data/marts.json
```

- [ ] **Step 2: Replace `dashboard/app/page.tsx`**

```tsx
import martsJson from "@/public/data/marts.json";
import { ChannelBarChart } from "@/components/ChannelBarChart";
import { KpiCards } from "@/components/KpiCards";
import { MonthlyLineChart } from "@/components/MonthlyLineChart";
import { parseMarts } from "@/lib/marts";

export default function Home() {
  const marts = parseMarts(martsJson);
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold">CampaignFlow</h1>
        <p className="text-sm text-gray-500">
          Spend, CTR, and cost-per-conversion across marketing channels.
        </p>
      </header>

      <KpiCards totals={marts.totals} />

      <div className="grid gap-6 md:grid-cols-3">
        <ChannelBarChart data={marts.channels} dataKey="spend_dkk" title="Spend by channel" />
        <ChannelBarChart data={marts.channels} dataKey="ctr_pct" title="CTR % by channel" />
        <ChannelBarChart
          data={marts.channels}
          dataKey="cost_per_conversion"
          title="Cost / conversion by channel"
        />
      </div>

      <MonthlyLineChart data={marts.monthly} />

      <footer className="text-xs text-gray-400">
        Generated {marts.generated_at} · seed {marts.seed}
      </footer>
    </main>
  );
}
```

- [ ] **Step 3: Set the page title in `dashboard/app/layout.tsx`**

Change the exported `metadata` to:

```tsx
export const metadata = {
  title: "CampaignFlow Dashboard",
  description: "Marketing-campaign spend, CTR, and cost-per-conversion.",
};
```

- [ ] **Step 4: Typecheck, test, and build**

Run:
```bash
cd dashboard && npm run typecheck && npm run test && npm run build && cd ..
```
Expected: typecheck clean, all Vitest tests pass, `next build` succeeds.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/page.tsx dashboard/app/layout.tsx dashboard/public/data/marts.json
git commit -m "feat(dashboard): compose the gold-marts dashboard page"
```

---

### Task 11: CI job for the dashboard

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a `dashboard` job running typecheck, Vitest, and `next build` against the committed fixture (no Python/Java/Azurite).

- [ ] **Step 1: Add the job**

Add a second job under `jobs:` (sibling to `test`):

```yaml
  dashboard:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm run test
      - run: npm run build
```

- [ ] **Step 2: Validate the workflow locally (optional)**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no error (valid YAML).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: build and test the dashboard app"
```

---

### Task 12: Documentation

**Files:**
- Modify: `README.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Add a dashboard section + mark roadmap #3 done**

Add a `## Dashboard` section after the *Blob landing zone* section:

```markdown
## Dashboard

A static Next.js + TypeScript dashboard over the gold marts lives in `dashboard/`.
The Python side exports the marts to JSON; the app renders them with Recharts —
no database or server at runtime.

```bash
python -m campaignflow run                 # build the warehouse
python -m campaignflow export              # -> dashboard/public/data/marts.json
cd dashboard && npm ci && npm run dev      # http://localhost:3000
```

Tests: `cd dashboard && npm test` (Vitest + Testing Library) run against a committed
fixture, so the Node suite needs no Python. CI builds and tests the app in its own job.
```

Under Roadmap, change item 3 to:

```markdown
3. ~~**Next.js / TypeScript dashboard**~~ — done (see *Dashboard* above).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: dashboard usage and roadmap update"
```

---

### Task 13: Open the PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feat/dashboard
gh pr create --base main --head feat/dashboard \
  --title "feat(dashboard): static Next.js dashboard over the gold marts" \
  --body "Implements roadmap #3. Build-time JSON export (campaignflow export) feeds a static Next.js + Recharts + Tailwind app under dashboard/. Python export reconciles to the fact; Node tests run against a committed fixture. New CI job builds and tests the app."
```

- [ ] **Step 2: Confirm both CI jobs are green**

Run: `gh run watch --exit-status` (select the latest run) — both `test` and `dashboard` jobs must pass.

---

## Self-review notes

- **Spec coverage:** export contract (T1–T2), CLI (T3), scaffold+fixture (T4), format (T5), marts parse (T6), KPI cards (T7), channel charts (T8), monthly chart+toggle (T9), page (T10), CI (T11), docs (T12), PR (T13). All spec sections covered.
- **Determinism:** `build_marts`/`export_marts` take `generated_at`; only the CLI calls `datetime.now`. Matches the global constraint.
- **Type consistency:** Python dict keys in T1 match the TS interfaces in T6 exactly (`spend_dkk`, `ctr_pct`, `cost_per_conversion`, `channel_group`, `channel_name`, `year_month`).
- **jsdom/Recharts caveat** is handled by asserting on the `sr-only` list and headings, not SVG.
- **Fixture** is generated once (T4) and also copied to `public/data` (T10) so both the app build and the Node tests are hermetic.
