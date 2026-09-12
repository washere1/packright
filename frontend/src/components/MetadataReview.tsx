import { useEffect, useState } from "react";
import { api, uploadAsset } from "../api";
import type { HandlingEdit, ItemReview, OrientationId, PreviewRecord } from "../contracts";

const ORIENTATIONS: OrientationId[] = ["xyz", "xzy", "yxz", "yzx", "zxy", "zyx"];

export function MetadataReview({ itemId, onReady, onDeleted }: { itemId: string; onReady?: () => void; onDeleted?: () => void }) {
  const [review, setReview] = useState<ItemReview | null>(null);
  const [previews, setPreviews] = useState<PreviewRecord[]>([]);
  const [name, setName] = useState(""); const [weight, setWeight] = useState("");
  const [priority, setPriority] = useState<1 | 2 | 3 | 4 | 5>(3);
  const [handling, setHandling] = useState<HandlingEdit | null>(null);
  const [ackScale, setAckScale] = useState(false); const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [activePreview, setActivePreview] = useState(0);
  const [scaleCorrection, setScaleCorrection] = useState("1");

  const load = async () => {
    const next = await api.getReview(itemId); setReview(next); setName(next.item.name ?? "");
    setWeight(String(next.item.weight_g)); setPriority(next.item.priority_stars);
    setScaleCorrection(String(next.item.geometry?.scale_correction ?? 1));
    if (next.item.handling) setHandling({
      category: next.item.handling.category, fragility: next.item.handling.fragility,
      compressibility: next.item.handling.compressibility, stack_class: next.item.handling.stack_class,
      can_support_weight: next.item.handling.can_support_weight, liquid_risk: next.item.handling.liquid_risk,
      legal_orientations: next.item.handling.legal_orientations, access: next.item.handling.access,
    });
    setPreviews(await api.previews(itemId, next.item.geometry?.version));
  };
  useEffect(() => { void load().catch(error => setMessage(error.message)); }, [itemId]);
  if (!review || !handling || !review.item.geometry) return <section className="review-card"><p>{message ?? "Loading review…"}</p></section>;
  const item = review.item, geometry = review.item.geometry!;
  const images = previews.filter(preview => preview.view !== "thumbnail");
  const updateHandling = <K extends keyof HandlingEdit>(key: K, value: HandlingEdit[K]) => setHandling(current => current ? { ...current, [key]: value } : current);
  const confirm = async () => {
    const parsedWeight = Number(weight);
    if (!name.trim()) { setMessage("Name is required before an item can be marked ready."); return; }
    if (!weight.trim() || !Number.isFinite(parsedWeight) || parsedWeight <= 0) { setMessage("Enter a positive weight in grams."); return; }
    setBusy(true); setMessage(null);
    try {
      await api.confirmItem(itemId, { name, weight_g: parsedWeight, priority_stars: priority, handling, acknowledge_scale: ackScale });
      setMessage("Item saved to your reusable library."); await load(); onReady?.();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save item."); } finally { setBusy(false); }
  };
  const replace = async (file: File) => {
    setBusy(true); setMessage("Replacing and reprocessing model…");
    try {
      await uploadAsset(itemId, file, () => {}); const nextGeometry = await api.processItem(itemId);
      try { const { captureAndUploadPreviews } = await import("../three/capturePreviews"); await captureAndUploadPreviews(itemId, nextGeometry); } catch { /* enrichment records explicit missing-preview fallback */ }
      await api.enrichItem(itemId); setAckScale(false); await load(); setMessage("Replacement model is ready to review.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Replacement failed."); } finally { setBusy(false); }
  };
  const applyScale = async () => {
    setBusy(true); setMessage("Regenerating geometry and previews…");
    try {
      const nextGeometry = await api.processItem(itemId, Number(scaleCorrection));
      try { const { captureAndUploadPreviews } = await import("../three/capturePreviews"); await captureAndUploadPreviews(itemId, nextGeometry); } catch { /* explicit fallback below */ }
      await api.enrichItem(itemId); setAckScale(false); await load(); setMessage("Scale correction applied; please review the new dimensions.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not apply scale correction."); } finally { setBusy(false); }
  };
  return <section className="review-card" aria-label="Item review">
    <div className="review-heading"><div><p className="eyebrow">REVIEW ITEM</p><h2>{name || "Unnamed item"}</h2></div><span className={`readiness ${item.stage}`}>{item.stage.replaceAll("_", " ")}</span></div>
    {images.length > 0 ? <div className="interactive-preview">
      <img src={`/api/previews/${images[activePreview % images.length].id}`} alt={`${images[activePreview % images.length].view} canonical model view`} />
      <div>{images.map((preview, index) => <button type="button" className={index === activePreview ? "active" : ""} onClick={() => setActivePreview(index)} key={preview.id}>{preview.view.replaceAll("_", " ")}</button>)}</div>
    </div> : <p className="notice warning">Preview regeneration is unavailable. Showing the canonical dimension box below as the persistent fallback.</p>}
    <div className="review-facts"><span><small>Dimensions</small>{geometry.canonical_dimensions_mm.width.toFixed(0)} × {geometry.canonical_dimensions_mm.height.toFixed(0)} × {geometry.canonical_dimensions_mm.depth.toFixed(0)} mm</span><span><small>Weight</small>{Number(weight || 0).toLocaleString()} g</span><span><small>Priority</small>{"★".repeat(priority)}{"☆".repeat(5 - priority)}</span><span><small>Handling</small>{handling.fragility} fragility · {handling.stack_class.replaceAll("_", " ")}</span></div>
    <p className="provenance">Suggested by {item.handling?.provenance.replaceAll("_", " ")}; your confirmed version is stored separately.</p>
    {review.questions.map(question => <div className="review-question" key={question}>
      <strong>{question === "suspicious_scale" ? "Does this scale look correct?" : question === "liquid_container" ? "Is this a liquid container?" : "Please verify the suggested handling."}</strong>
      {question === "suspicious_scale" && <><label><input type="checkbox" checked={ackScale} onChange={event => setAckScale(event.target.checked)} /> I confirm these dimensions are correct</label><div className="scale-fix"><label>Uniform scale correction<input type="number" min="0.001" max="1000" step="0.01" value={scaleCorrection} onChange={event => setScaleCorrection(event.target.value)} /></label><button type="button" className="secondary" disabled={busy || !(Number(scaleCorrection) > 0)} onClick={applyScale}>Apply & regenerate</button></div></>}
    </div>)}
    <div className="quick-edits"><label>Name<input value={name} onChange={event => setName(event.target.value)} /></label><label>Weight (g)<input type="number" min="1" value={weight} onChange={event => setWeight(event.target.value)} /></label><fieldset><legend>Trip default priority</legend><div className="stars compact">{([1,2,3,4,5] as const).map(star => <button type="button" className={star <= priority ? "selected" : ""} onClick={() => setPriority(star)} aria-label={`${star} stars`} key={star}>★</button>)}</div></fieldset></div>
    <details className="edit-drawer"><summary>Edit handling details</summary><div className="drawer-grid">
      <label>Category<input value={handling.category} onChange={event => updateHandling("category", event.target.value)} /></label>
      <label>Fragility<select value={handling.fragility} onChange={event => updateHandling("fragility", event.target.value as HandlingEdit["fragility"])}><option>low</option><option>medium</option><option>high</option></select></label>
      <label>Compression<select value={handling.compressibility} onChange={event => updateHandling("compressibility", event.target.value as HandlingEdit["compressibility"])}><option>none</option><option>light</option><option>high</option></select></label>
      <label>Stack class<select value={handling.stack_class} onChange={event => { const value = event.target.value as HandlingEdit["stack_class"]; setHandling(current => current ? { ...current, stack_class: value, can_support_weight: value === "top_only" ? false : current.can_support_weight } : current); }}><option>base</option><option>neutral</option><option value="top_only">top only</option></select></label>
      <label>Access<select value={handling.access} onChange={event => updateHandling("access", event.target.value as HandlingEdit["access"])}><option value="buried_ok">buried okay</option><option>normal</option><option>quick</option></select></label>
      <label className="check"><input type="checkbox" checked={handling.can_support_weight} disabled={handling.stack_class === "top_only"} onChange={event => updateHandling("can_support_weight", event.target.checked)} /> Can support weight</label>
      <label className="check"><input type="checkbox" checked={handling.liquid_risk} onChange={event => updateHandling("liquid_risk", event.target.checked)} /> Liquid risk</label>
      <fieldset className="orientations"><legend>Allowed canonical orientations</legend>{ORIENTATIONS.map(orientation => <label key={orientation}><input type="checkbox" checked={handling.legal_orientations.includes(orientation)} onChange={event => updateHandling("legal_orientations", event.target.checked ? [...handling.legal_orientations, orientation] : handling.legal_orientations.filter(value => value !== orientation))} />{orientation.toUpperCase()}</label>)}</fieldset>
    </div></details>
    <div className="review-actions"><button className="primary" type="button" disabled={busy} onClick={confirm}>Save item</button><label className="secondary file-action">Replace model<input className="visually-hidden" type="file" accept=".glb" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) void replace(file); }} /></label><button className="danger" type="button" disabled={busy} onClick={() => void api.deleteItem(itemId).then(() => onDeleted?.()).catch(error => setMessage(error instanceof Error ? error.message : "Could not archive item."))}>Archive item</button></div>
    {message && <p className="notice">{message}</p>}
  </section>;
}
