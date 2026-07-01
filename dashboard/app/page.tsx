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
