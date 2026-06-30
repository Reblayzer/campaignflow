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
                <span>{d.channel_name}</span>: {String(d[dataKey])}
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
