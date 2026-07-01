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
