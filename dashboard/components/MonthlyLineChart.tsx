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
