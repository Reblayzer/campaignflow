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
