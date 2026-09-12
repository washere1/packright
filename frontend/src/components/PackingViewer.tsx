import { useEffect, useMemo, useState } from "react";
import type { LibraryItem, PackingPlan, Suitcase } from "../contracts";
import { PackingStepper } from "./PackingStepper";
import { PackingScene } from "../viewer/PackingScene";

const palette = ["#2c7655", "#c17b2d", "#5877a8", "#9b5d75", "#6f6a9c", "#6d8d4a"];

export function PackingViewer({ plan, suitcase, catalog }: { plan: PackingPlan; suitcase: Suitcase; catalog: LibraryItem[] }) {
  const [step, setStep] = useState(plan.placements.length);
  const [xray, setXray] = useState(false);
  const [meshes, setMeshes] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [meshFailure, setMeshFailure] = useState<string | null>(null);
  const [showShell, setShowShell] = useState(true); const [showClearance, setShowClearance] = useState(true); const [showCom, setShowCom] = useState(true);
  const [resetToken, setResetToken] = useState(0);
  useEffect(() => { setStep(plan.placements.length); setSelected(null); setMeshFailure(null); }, [plan.id, plan.placements.length]);
  const items = useMemo(() => new Map(catalog.map(item => [item.id, item])), [catalog]);
  const visible = plan.placements.filter(placement => placement.packing_order <= step);
  useEffect(() => { if (meshes && visible.length > 12) setMeshFailure("Detailed mesh mode exceeded the local scene budget."); }, [meshes, visible.length]);
  const selectedPlacement = visible.find(item => item.instance_id === selected) ?? visible.at(-1);
  const colors = useMemo(() => new Map(plan.placements.map((placement, index) => [placement.instance_id, palette[index % palette.length]])), [plan.placements]);
  const snapshotSuitcase = plan.snapshot?.trip.suitcase ?? suitcase;
  const instruction = selectedPlacement ? plan.instructions.find(value => value.instance_id === selectedPlacement.instance_id) : undefined;
  const selectedItem = selectedPlacement ? items.get(selectedPlacement.item_id) : undefined;
  return <section className="packing-viewer" aria-label="Interactive packing viewer">
    <div className="viewer-heading"><div><p className="eyebrow">PACKING VIEWER</p><h2>{plan.state === "feasible" ? "Your validated arrangement" : "Search result"}</h2></div><span className="viewer-step">{visible.length} / {plan.placements.length} visible</span></div>
    <div className="viewer-stage three-stage"><PackingScene placements={visible} suitcase={snapshotSuitcase} catalog={catalog} colors={colors} xray={xray} detailedMeshes={meshes && !meshFailure} showShell={showShell} showClearance={showClearance} showCom={showCom} resetToken={resetToken} onMeshFailure={setMeshFailure} onSelect={setSelected} /><div className="viewer-axis">X width · Y vertical · Z wheel side toward opening</div><span className="scene-label wheel-label">Wheel side</span><span className="scene-label opening-label">Opening</span></div>
    {meshFailure && <p className="notice warning" role="status">{meshFailure} Switched to validated cuboids.</p>}
    <PackingStepper step={step} total={plan.placements.length} xray={xray} meshes={meshes && !meshFailure} onStep={next => setStep(next)} onXray={() => setXray(value => !value)} onMeshes={() => { setMeshFailure(null); setMeshes(value => !value); }} />
    <div className="viewer-controls layer-controls" aria-label="Viewer layers"><button className="secondary" onClick={() => setShowShell(value => !value)}>{showShell ? "Hide suitcase" : "Show suitcase"}</button><button className="secondary" onClick={() => setShowClearance(value => !value)}>{showClearance ? "Hide clearance" : "Show clearance"}</button><button className="secondary" onClick={() => setShowCom(value => !value)}>{showCom ? "Hide COM target" : "Show COM target"}</button></div>
    <div className="viewer-controls viewer-camera"><button className="secondary" onClick={() => { setStep(plan.placements.length); setXray(false); setMeshes(true); setMeshFailure(null); setResetToken(value => value + 1); }}>Reset camera & layers</button></div>
    <div className="viewer-legend">{Array.from(new Set(visible.map(item => items.get(item.item_id)?.category ?? "Other"))).map((category, index) => <span key={category}><i style={{ background: palette[index % palette.length] }} />{category}</span>)}</div>
    <div className="viewer-items" aria-label="Visible packed items">{visible.map(placement => <button key={placement.instance_id} className={selectedPlacement?.instance_id === placement.instance_id ? "selected" : ""} onClick={() => setSelected(placement.instance_id)}><i style={{ background: colors.get(placement.instance_id) }} />{items.get(placement.item_id)?.name ?? "Packed item"} · step {placement.packing_order}</button>)}</div>
    <section className="viewer-selection" aria-live="polite"><h3>{selectedItem?.name ?? "Select an item"}</h3>{selectedPlacement && <p>Copy {instruction?.copy_number ?? "?"} · {instruction?.destination ?? "packed position"} · orientation {selectedPlacement.orientation_id} · {selectedItem?.weight_g ?? "?"} g</p>}{selectedPlacement && <p>{selectedItem?.handling?.category ?? "Other"} · {selectedItem?.handling?.access ?? "normal"} access · {selectedPlacement.support_ratio * 100}% support · validated padded box</p>}</section>
    <small className="viewer-disclaimer">Detailed meshes are visual context only. The independent validator uses the snapshot’s padded cuboids and does not prove an insertion trajectory. Center of mass is a heuristic target, not a stability guarantee.</small>
  </section>;
}
