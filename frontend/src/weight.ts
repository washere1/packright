import type { WeightUnit } from "./contracts";

const GRAMS_PER_UNIT: Record<WeightUnit, number> = {
  g: 1,
  kg: 1000,
  oz: 28.349523125,
  lb: 453.59237,
};

export function toGrams(value: number, unit: WeightUnit): number {
  return value * GRAMS_PER_UNIT[unit];
}

export interface RequiredInputs {
  file: { name: string; size: number } | null;
  weightText: string;
  weightUnit: WeightUnit;
  priority: number | null;
}

export function validateRequiredInputs(inputs: RequiredInputs, maxBytes: number, maxWeightG: number) {
  const errors: Partial<Record<"file" | "weight" | "priority", string>> = {};
  if (!inputs.file) errors.file = "Select a GLB model.";
  else if (!inputs.file.name.toLowerCase().endsWith(".glb")) errors.file = "Select a file ending in .glb.";
  else if (inputs.file.size > maxBytes) errors.file = "The GLB must be 50 MB or smaller.";

  const weight = Number(inputs.weightText);
  const weightG = toGrams(weight, inputs.weightUnit);
  if (!inputs.weightText.trim() || !Number.isFinite(weight) || weight <= 0) errors.weight = "Enter a positive finite weight.";
  else if (weightG > maxWeightG) errors.weight = "Weight must be 100 kg or less.";
  if (inputs.priority === null || !Number.isInteger(inputs.priority) || inputs.priority < 1 || inputs.priority > 5) {
    errors.priority = "Choose a priority from one to five stars.";
  }
  return { errors, weightG };
}

