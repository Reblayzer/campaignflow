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
