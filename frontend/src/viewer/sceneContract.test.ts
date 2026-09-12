import { describe, expect, it } from "vitest";
import type { Placement, Suitcase } from "../contracts";
import { placementCenter, placementInsideSuitcase, sceneContract } from "./sceneContract";

const suitcase: Suitcase = { id: "case", name: "Judge carry-on", internal_dimensions_mm: { width: 550, height: 350, depth: 230 }, clearance_mm: 10, empty_weight_g: 2500, baggage_limit_g: 10000, display_length_unit: "mm", display_weight_unit: "g" };
const placement: Placement = { instance_id: "instance", item_id: "item", position_mm: [20, 30, 40], dimensions_mm: { width: 100, height: 80, depth: 60 }, orientation_id: "xyz", orientation_matrix: { values: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] }, packing_order: 1, support_ratio: 1 };

describe("viewer scene contract", () => {
  it("offsets solver coordinates into the clearance envelope", () => {
    const contract = sceneContract(suitcase);
    expect(contract.usable.toArray()).toEqual([540, 340, 220]);
    expect(contract.usableOrigin.toArray()).toEqual([5, 5, 5]);
    expect(placementCenter(placement, contract).toArray()).toEqual([75, 75, 75]);
  });

  it("accepts boundary-touching boxes and rejects overflow on every axis", () => {
    const contract = sceneContract(suitcase);
    const exact = { ...placement, position_mm: [440, 260, 160] as [number, number, number] };
    expect(placementInsideSuitcase(exact, contract)).toBe(true);
    for (const position of [[441, 260, 160], [440, 261, 160], [440, 260, 161]] as [number, number, number][]) expect(placementInsideSuitcase({ ...placement, position_mm: position }, contract)).toBe(false);
  });
});
