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
