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
