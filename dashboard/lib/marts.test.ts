import { describe, expect, it } from "vitest";
import fixture from "../fixtures/marts.json";
import { parseMarts } from "./marts";

describe("parseMarts", () => {
  it("accepts the committed fixture and exposes typed fields", () => {
    const marts = parseMarts(fixture);
    expect(marts.channels.length).toBe(6);
    expect(typeof marts.totals.spend_dkk).toBe("number");
    expect(marts.monthly[0].year_month).toMatch(/^\d{4}-\d{2}$/);
  });
  it("throws on a malformed shape", () => {
    expect(() => parseMarts({ totals: {} })).toThrow();
  });
});
