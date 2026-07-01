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
