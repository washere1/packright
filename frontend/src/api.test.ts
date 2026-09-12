import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { toGrams, validateRequiredInputs } from "./weight";
import { isStarFilled } from "./components/RequiredItemInputs";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("reads a health response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", service: "packright-api", api_version: "0.1.0" }), { status: 200 })));
    await expect(api.health()).resolves.toEqual({ status: "ok", service: "packright-api", api_version: "0.1.0" });
  });

  it("creates a trip with every selected item in one request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ trip: { id: "trip-1", name: "Judge trip", suitcase: {}, items: [] }, requested_item_weight_g: 0, available_item_weight_g: 0, total_utility: 0, warnings: [] }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.createTrip("Judge trip", { id: "case-1", name: "Carry-on", internal_dimensions_mm: { width: 550, height: 350, depth: 230 }, empty_weight_g: 2500, baggage_limit_g: 10000, clearance_mm: 8, display_length_unit: "mm", display_weight_unit: "g" }, ["item-a", "item-b", "item-c"]);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({ selected_item_ids: ["item-a", "item-b", "item-c"] });
  });

  it("requests archived custom items and can restore one", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.library("custom", "", "", "archived");
    expect(fetchMock.mock.calls[0][0]).toContain("lifecycle=archived");
  });
});

describe("required item inputs", () => {
  it("fills every star up to the selected rating", () => {
    expect([1, 2, 3, 4, 5].map(star => isStarFilled(star, 3))).toEqual([true, true, true, false, false]);
    expect([1, 2, 3, 4, 5].map(star => isStarFilled(star, 1))).toEqual([true, false, false, false, false]);
    expect([1, 2, 3, 4, 5].map(star => isStarFilled(star, 5))).toEqual([true, true, true, true, true]);
  });
  it("converts supported display units to grams", () => {
    expect(toGrams(1, "kg")).toBe(1000);
    expect(toGrams(1, "lb")).toBeCloseTo(453.59237);
    expect(toGrams(1, "oz")).toBeCloseTo(28.349523125);
  });

  it("requires one GLB, a bounded positive weight, and one-to-five stars", () => {
    const missing = validateRequiredInputs({ file: null, weightText: "", weightUnit: "g", priority: null }, 50, 100_000);
    expect(Object.keys(missing.errors)).toEqual(["file", "weight", "priority"]);

    const valid = validateRequiredInputs({ file: { name: "Mouse.glb", size: 40 }, weightText: "94", weightUnit: "g", priority: 4 }, 50, 100_000);
    expect(valid).toEqual({ errors: {}, weightG: 94 });
  });

  it("rejects malformed filenames, oversized files, and nonfinite weight", () => {
    expect(validateRequiredInputs({ file: { name: "Mouse.obj", size: 1 }, weightText: "1", weightUnit: "g", priority: 1 }, 50, 100_000).errors.file).toBeTruthy();
    expect(validateRequiredInputs({ file: { name: "Mouse.glb", size: 51 }, weightText: "1", weightUnit: "g", priority: 1 }, 50, 100_000).errors.file).toBeTruthy();
    expect(validateRequiredInputs({ file: { name: "Mouse.glb", size: 1 }, weightText: "Infinity", weightUnit: "g", priority: 1 }, 50, 100_000).errors.weight).toBeTruthy();
  });
});
