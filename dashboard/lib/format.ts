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
