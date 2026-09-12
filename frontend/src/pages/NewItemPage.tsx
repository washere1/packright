import { useState, type FormEvent } from "react";
import { api, uploadAsset } from "../api";
import type { EnrichmentResult, Geometry, PreviewRecord, PublicConfigResponse, WeightUnit } from "../contracts";
import { ModelUploader } from "../components/ModelUploader";
import { RequiredItemInputs } from "../components/RequiredItemInputs";
import { toGrams, validateRequiredInputs } from "../weight";
import { ItemScene } from "../three/ItemScene";
import { MetadataReview } from "../components/MetadataReview";

type SubmitStage = "idle" | "saving" | "uploading" | "geometry" | "previews" | "enrichment" | "complete" | "error";

export function NewItemPage({ config }: { config: PublicConfigResponse }) {
  const [file, setFile] = useState<File | null>(null);
  const [weight, setWeight] = useState("");
  const [unit, setUnit] = useState<WeightUnit>("g");
  const [priority, setPriority] = useState<number | null>(null);
  const [errors, setErrors] = useState<{ file?: string; weight?: string; priority?: string }>({});
  const [stage, setStage] = useState<SubmitStage>("idle");
  const [draftSaved, setDraftSaved] = useState(false);
  const [uploadStarted, setUploadStarted] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ loaded: number; total: number | null }>({ loaded: 0, total: null });
  const [message, setMessage] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [previews, setPreviews] = useState<PreviewRecord[]>([]);
  const [enrichment, setEnrichment] = useState<EnrichmentResult | null>(null);
  const [renderingFailed, setRenderingFailed] = useState(false);
  const [itemId, setItemId] = useState<string | null>(null);
  const busy = !["idle", "complete", "error"].includes(stage);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const checked = validateRequiredInputs({ file, weightText: weight, weightUnit: unit, priority }, config.limits.max_upload_bytes, config.limits.max_item_weight_g);
    setErrors(checked.errors);
    setMessage(null);
    setWarnings([]);
    setGeometry(null); setPreviews([]); setEnrichment(null); setRenderingFailed(false);
    setDraftSaved(false);
    setUploadStarted(false);
    if (Object.keys(checked.errors).length || !file || priority === null) return;

    try {
      setStage("saving");
      const draft = await api.createDraft({
        weight_g: toGrams(Number(weight), unit),
        priority_stars: priority as 1 | 2 | 3 | 4 | 5,
        display_weight_unit: unit,
      });
      setItemId(draft.id);
      setDraftSaved(true);
      setStage("uploading");
      setUploadStarted(true);
      setUploadProgress({ loaded: 0, total: file.size });
      const result = await uploadAsset(draft.id, file, (loaded, total) => {
        setUploadProgress({ loaded, total });
        if (total !== null && loaded >= total) setStage("geometry");
      });
      setWarnings(result.warnings);
      setStage("geometry");
      const extracted = await api.processItem(draft.id);
      setGeometry(extracted);
      setWarnings(current => [...current, ...extracted.warnings]);
      setStage("previews");
      try {
        const { captureAndUploadPreviews } = await import("../three/capturePreviews");
        setPreviews(await captureAndUploadPreviews(draft.id, extracted));
      } catch (renderError) {
        setRenderingFailed(true);
        setWarnings(current => [...current, renderError instanceof Error ? renderError.message : "Model previews were unavailable."]);
      }
      setStage("enrichment");
      const enriched = await api.enrichItem(draft.id);
      setEnrichment(enriched);
      setStage("complete");
      setMessage(enriched.fallback_reason
        ? `Item processed with neutral metadata fallback (${enriched.fallback_reason.replaceAll("_", " ")}).`
        : `Item processed with ${enriched.provider} metadata${enriched.cached ? " from cache" : ""}.`);
    } catch (reason) {
      setStage("error");
      setMessage(reason instanceof Error ? reason.message : "The item could not be uploaded. Your inputs are still here.");
    }
  };

  const percent = uploadProgress.total && uploadProgress.total > 0
    ? Math.min(100, Math.round(uploadProgress.loaded / uploadProgress.total * 100)) : null;

  return (
    <main className="new-item-page">
      <header className="page-header">
        <p className="eyebrow">ITEM LIBRARY</p>
        <h1>Add an item</h1>
        <p>Upload one 3D model and tell PackRight how much the item matters.</p>
      </header>

      <form onSubmit={submit} noValidate>
        <ModelUploader file={file} error={errors.file} disabled={busy} onChange={next => { setFile(next); setErrors(current => ({ ...current, file: undefined })); }} />
        <RequiredItemInputs weight={weight} unit={unit} priority={priority} errors={errors} disabled={busy}
          onWeightChange={value => { setWeight(value); setErrors(current => ({ ...current, weight: undefined })); }}
          onUnitChange={setUnit} onPriorityChange={value => { setPriority(value); setErrors(current => ({ ...current, priority: undefined })); }} />
        <button className="primary" type="submit" disabled={busy}>{busy ? "Saving item…" : "Save and process"}</button>
      </form>

      {stage !== "idle" && (
        <section className="processing" aria-live="polite" aria-label="Item processing status">
          <h2>Processing status</h2>
          <ol>
            <li data-state={stage === "saving" ? "active" : draftSaved ? "done" : "waiting"}><span>1</span><div><strong>Draft</strong><small>{stage === "saving" ? "Saving required inputs…" : draftSaved ? "Saved" : "Not saved"}</small></div></li>
            <li data-state={stage === "uploading" ? "active" : uploadStarted ? "done" : "waiting"}><span>2</span><div><strong>Upload</strong><small>{stage === "uploading" ? (percent === null ? `${uploadProgress.loaded.toLocaleString()} bytes sent` : `${percent}% sent`) : uploadStarted ? "Completed" : "Waiting"}</small>{stage === "uploading" && percent !== null && <progress value={uploadProgress.loaded} max={uploadProgress.total ?? 1}>{percent}%</progress>}</div></li>
            <li data-state={stage === "geometry" ? "active" : geometry ? "done" : "waiting"}><span>3</span><div><strong>Geometry</strong><small>{stage === "geometry" ? "Extracting canonical bounds…" : geometry ? "Canonical geometry saved" : stage === "error" && uploadStarted ? "Processing failed" : "Waiting"}</small></div></li>
            <li data-state={stage === "previews" ? "active" : geometry && ["enrichment", "complete"].includes(stage) ? "done" : "waiting"}><span>4</span><div><strong>Previews</strong><small>{stage === "previews" ? "Rendering four canonical views…" : previews.length === 4 ? "Four views stored" : renderingFailed ? "Using dimension fallback" : "Waiting"}</small></div></li>
            <li data-state={stage === "enrichment" ? "active" : enrichment ? "done" : "waiting"}><span>5</span><div><strong>Enrichment</strong><small>{stage === "enrichment" ? "Validating suggested handling…" : enrichment ? (enrichment.fallback_reason ? "Neutral fallback saved" : "Suggestion saved") : "Waiting"}</small></div></li>
          </ol>
          {message && <p className={stage === "error" ? "notice error" : "notice"}>{message}</p>}
          {warnings.map(warning => <p className="notice warning" key={warning}>{warning}</p>)}
        </section>
      )}
      {geometry && <ItemScene geometry={geometry} previews={previews} renderingFailed={renderingFailed} />}
      {enrichment && <section className="metadata-card" aria-label="Metadata suggestion">
        <div><p className="eyebrow">SUGGESTED METADATA</p><h2>{enrichment.suggestion.name}</h2></div>
        <dl>
          <div><dt>Category</dt><dd>{enrichment.suggestion.category}</dd></div>
          <div><dt>Fragility</dt><dd>{enrichment.suggestion.fragility}</dd></div>
          <div><dt>Compression</dt><dd>{enrichment.suggestion.compressibility}</dd></div>
          <div><dt>Stacking</dt><dd>{enrichment.suggestion.stack_class.replaceAll("_", " ")}</dd></div>
          <div><dt>Access</dt><dd>{enrichment.suggestion.access.replaceAll("_", " ")}</dd></div>
          <div><dt>Liquid risk</dt><dd>{enrichment.suggestion.liquid_risk ? "Yes" : "No"}</dd></div>
        </dl>
        <p>{enrichment.suggestion.short_reason}</p>
        <small>Source: {enrichment.provider} · {enrichment.model_id} · prompt {enrichment.prompt_version}</small>
        {config.capabilities.live_enrichment_configured && !enrichment.fallback_reason && <p className="provider-note">Live enrichment sent the four generated previews to the configured model provider. Weight and priority were not sent or changed.</p>}
        {enrichment.fallback_reason && <p className="notice warning">Automated visual inference was unavailable. Conservative metadata was used and should be reviewed.</p>}
      </section>}
      {stage === "complete" && itemId && <MetadataReview itemId={itemId} />}
    </main>
  );
}
