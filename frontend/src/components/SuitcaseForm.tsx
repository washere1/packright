import { useEffect, useState } from "react";
import { api } from "../api";
import type { LengthUnit, Suitcase, SuitcaseBoundaryRequest, WeightUnit } from "../contracts";

const lengthFactor: Record<LengthUnit, number> = { mm: 1, cm: 10, in: 25.4 };
const weightFactor: Record<WeightUnit, number> = { g: 1, kg: 1000, oz: 28.349523125, lb: 453.59237 };

function boundaryFrom(suitcase: Suitcase, lengthUnit: LengthUnit, weightUnit: WeightUnit): SuitcaseBoundaryRequest {
  return { name: suitcase.name, width: suitcase.internal_dimensions_mm.width / lengthFactor[lengthUnit],
    height: suitcase.internal_dimensions_mm.height / lengthFactor[lengthUnit], depth: suitcase.internal_dimensions_mm.depth / lengthFactor[lengthUnit],
    length_unit: lengthUnit, empty_weight: suitcase.empty_weight_g / weightFactor[weightUnit],
    baggage_limit: suitcase.baggage_limit_g / weightFactor[weightUnit], weight_unit: weightUnit,
    clearance_mm: suitcase.clearance_mm };
}

export function SuitcaseForm({ suitcase, onChange, availableWeight }: { suitcase: Suitcase; onChange: (value: Suitcase) => void; availableWeight: number }) {
  const [lengthUnit, setLengthUnit] = useState<LengthUnit>(suitcase.display_length_unit);
  const [weightUnit, setWeightUnit] = useState<WeightUnit>(suitcase.display_weight_unit);
  const [draft, setDraft] = useState(() => boundaryFrom(suitcase, lengthUnit, weightUnit));
  const [presets, setPresets] = useState<Suitcase[]>([]); const [presetId, setPresetId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => { setDraft(boundaryFrom(suitcase, lengthUnit, weightUnit)); }, [suitcase.id]);
  useEffect(() => { void api.suitcases().then(setPresets); }, []);
  const commit = (next: SuitcaseBoundaryRequest) => {
    setDraft(next); onChange({ ...suitcase, name: next.name,
      internal_dimensions_mm: { width: next.width * lengthFactor[next.length_unit], height: next.height * lengthFactor[next.length_unit], depth: next.depth * lengthFactor[next.length_unit] },
      empty_weight_g: next.empty_weight * weightFactor[next.weight_unit], baggage_limit_g: next.baggage_limit * weightFactor[next.weight_unit],
      clearance_mm: next.clearance_mm, display_length_unit: next.length_unit, display_weight_unit: next.weight_unit });
  };
  const changeLengthUnit = (unit: LengthUnit) => { const canonical = { width: draft.width * lengthFactor[lengthUnit], height: draft.height * lengthFactor[lengthUnit], depth: draft.depth * lengthFactor[lengthUnit] }; setLengthUnit(unit); commit({ ...draft, width: canonical.width / lengthFactor[unit], height: canonical.height / lengthFactor[unit], depth: canonical.depth / lengthFactor[unit], length_unit: unit }); };
  const changeWeightUnit = (unit: WeightUnit) => { const empty = draft.empty_weight * weightFactor[weightUnit], limit = draft.baggage_limit * weightFactor[weightUnit]; setWeightUnit(unit); commit({ ...draft, empty_weight: empty / weightFactor[unit], baggage_limit: limit / weightFactor[unit], weight_unit: unit }); };
  const refresh = () => api.suitcases().then(setPresets);
  const savePreset = async () => { try { const saved = presetId ? await api.updateSuitcasePreset(presetId, draft) : await api.createSuitcase(draft); setPresetId(saved.id); await refresh(); setMessage("Suitcase preset saved. Trip changes remain independent."); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save preset."); } };
  const usePreset = (id: string) => { setPresetId(id); const selected = presets.find(value => value.id === id); if (!selected) return; setLengthUnit(selected.display_length_unit); setWeightUnit(selected.display_weight_unit); setDraft(boundaryFrom(selected, selected.display_length_unit, selected.display_weight_unit)); onChange({ ...selected, id: suitcase.id }); };
  const numeric = (key: keyof Pick<SuitcaseBoundaryRequest, "width" | "height" | "depth" | "empty_weight" | "baggage_limit" | "clearance_mm">, raw: string) => { if (raw === "") return; const value = Number(raw); if (!Number.isFinite(value)) return; commit({ ...draft, [key]: value }); };
  const usable = { width: suitcase.internal_dimensions_mm.width - suitcase.clearance_mm, height: suitcase.internal_dimensions_mm.height - suitcase.clearance_mm, depth: suitcase.internal_dimensions_mm.depth - suitcase.clearance_mm };
  return <section className="suitcase-card"><div className="suitcase-title"><div><p className="eyebrow">SUITCASE</p><h2>Internal packing space</h2></div><label>Saved preset<select value={presetId} onChange={event => usePreset(event.target.value)}><option value="">New preset</option>{presets.map(preset => <option value={preset.id} key={preset.id}>{preset.name}</option>)}</select></label></div>
    <div className="suitcase-layout"><div className="suitcase-diagram" aria-label="Suitcase axis diagram"><div className="case-face"><span className="axis axis-x">X · width</span><span className="axis axis-y">Y · height</span><span className="axis axis-z">Z · opening</span><b>Wheel side</b></div></div><div className="drawer-grid">
      <label>Name<input value={draft.name} onChange={event => commit({ ...draft, name: event.target.value })} /></label><label>Length unit<select value={lengthUnit} onChange={event => changeLengthUnit(event.target.value as LengthUnit)}><option value="mm">mm</option><option value="cm">cm</option><option value="in">inches</option></select></label>
      {(["width","height","depth"] as const).map(axis => <label key={axis}>{axis}<input type="number" min="0.01" value={draft[axis]} onChange={event => numeric(axis, event.target.value)} /></label>)}
      <label>Weight unit<select value={weightUnit} onChange={event => changeWeightUnit(event.target.value as WeightUnit)}><option value="g">g</option><option value="kg">kg</option><option value="oz">oz</option><option value="lb">lb</option></select></label><label>Empty weight<input type="number" min="0" value={draft.empty_weight} onChange={event => numeric("empty_weight", event.target.value)} /></label><label>Total baggage limit<input type="number" min="0.01" value={draft.baggage_limit} onChange={event => numeric("baggage_limit", event.target.value)} /></label>
    </div></div>
    <details className="edit-drawer"><summary>Advanced clearance</summary><label>Clearance — total reduction per axis (0–15 mm)<input type="number" min="0" max="15" value={draft.clearance_mm} onChange={event => numeric("clearance_mm", event.target.value)} /></label></details>
    <div className="usable-summary"><span><small>Usable dimensions</small>{usable.width.toFixed(1)} × {usable.height.toFixed(1)} × {usable.depth.toFixed(1)} mm</span><span><small>Available item weight</small>{availableWeight.toLocaleString()} g</span></div>
    <div className="library-actions"><button className="secondary" type="button" onClick={savePreset}>{presetId ? "Update preset" : "Save as preset"}</button>{presetId && <button className="danger" type="button" onClick={() => void api.deleteSuitcasePreset(presetId).then(() => { setPresetId(""); void refresh(); })}>Delete preset</button>}</div>{message && <p className="notice">{message}</p>}
  </section>;
}
