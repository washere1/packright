import { useEffect, useState } from "react";
import { api } from "./api";
import type { HealthResponse, LibraryItem, PackingPlan, PlanJob, ProcessingJob, PublicConfigResponse, Suitcase, TripSummary } from "./contracts";
import { NewItemPage } from "./pages/NewItemPage";
import { LibraryPage } from "./pages/LibraryPage";
import { TripBuilderPage } from "./pages/TripBuilderPage";
import { PlanPage } from "./pages/PlanPage";
import { MetadataReview } from "./components/MetadataReview";
import "./styles.css";

function PlanRoute({ planId }: { planId: string }) {
  const [plan, setPlan] = useState<PackingPlan | null>(null); const [summary, setSummary] = useState<TripSummary | null>(null); const [catalog, setCatalog] = useState<LibraryItem[]>([]); const [stale, setStale] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState<string | null>(null);
  useEffect(() => { void Promise.all([api.getPlan(planId), api.library()]).then(async ([nextPlan, nextCatalog]) => { setPlan(nextPlan); setCatalog(nextCatalog); setSummary(await api.getTrip(nextPlan.trip_id)); }).catch(error => setMessage(error instanceof Error ? error.message : "Could not reload this plan.")); }, [planId]);
  const replan = async (suitcase: Suitcase) => { if (!plan) return; setStale(true); setBusy(true); setMessage("Replanning with a new immutable snapshot…"); try { const job = await api.replanJob(plan.id, suitcase, undefined, `route-replan-${crypto.randomUUID()}`); for (let attempt = 0; attempt < 80; attempt += 1) { const state = await api.getPlanJob(job.id); if (state.status === "completed" && state.plan_id) { const next = await api.getPlan(state.plan_id); setPlan(next); setSummary(await api.getTrip(next.trip_id)); setStale(false); setMessage("Latest validator result loaded."); break; } if (state.status === "failed" || state.status === "retryable") throw new Error(state.error_message ?? "Replan failed."); await new Promise(resolve => window.setTimeout(resolve, 150)); } } catch (error) { setMessage(error instanceof Error ? error.message : "Replan failed; the baseline remains selected."); } finally { setBusy(false); } };
  if (!plan || !summary) return <main className="loading-shell" aria-live="polite"><h1>Loading saved plan…</h1><p>{message}</p></main>;
  return <main className="trip-page"><PlanPage plan={plan} summary={summary} catalog={catalog} stale={stale} busy={busy} onReplan={replan} />{message && <p className="notice" role="status">{message}</p>}</main>;
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [config, setConfig] = useState<PublicConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const initialPath = window.location.pathname;
  const [page, setPage] = useState<"add" | "library" | "trip" | "review" | "plan">(initialPath.startsWith("/library") ? "library" : initialPath.startsWith("/trips") ? "trip" : initialPath.startsWith("/plans/") ? "plan" : "add");
  const [routePlanId, setRoutePlanId] = useState<string | null>(initialPath.startsWith("/plans/") ? initialPath.split("/")[2] ?? null : null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [processingJobs, setProcessingJobs] = useState<ProcessingJob[]>([]); const [planJobs, setPlanJobs] = useState<PlanJob[]>([]);

  useEffect(() => {
    Promise.all([api.health(), api.config()])
      .then(([nextHealth, nextConfig]) => { setHealth(nextHealth); setConfig(nextConfig); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "API unavailable"));
  }, []);
  useEffect(() => { const refresh = () => { void api.processingStatus().then(setProcessingJobs).catch(() => undefined); void api.planJobs().then(setPlanJobs).catch(() => undefined); }; refresh(); const timer = window.setInterval(refresh, 3000); return () => window.clearInterval(timer); }, []);

  return (
    <>
      <nav className="topbar" aria-label="Primary navigation">
        <button className="brand" onClick={() => { window.history.pushState({}, "", "/items/new"); setPage("add"); }}>PackRight</button>
        <div className="nav-links"><button className={page === "add" ? "active" : ""} onClick={() => { window.history.pushState({}, "", "/items/new"); setPage("add"); }}>Add item</button><button className={page === "library" ? "active" : ""} onClick={() => { window.history.pushState({}, "", "/library"); setPage("library"); }}>Library</button><button className={page === "trip" ? "active" : ""} onClick={() => { window.history.pushState({}, "", "/trips/new"); setPage("trip"); }}>Trip</button></div>
        <span className="api-state"><i className={`status ${health ? "online" : ""}`} />{health ? "Local API online" : error ? "API offline" : "Connecting…"}</span>
      </nav>
      {(processingJobs.length > 0 || planJobs.some(job => job.status === "retryable" || job.status === "failed")) && <section className="recovery-banner" aria-live="polite"><strong>Recoverable work needs attention</strong>{processingJobs.map(job => <span key={job.id}>{job.operation_type === "geometry" ? "Retry geometry" : job.operation_type === "previews" ? "Open the browser to recreate previews" : "Use cuboid fallback and review metadata"} <button className="text-button" onClick={() => void api.retryProcessing(job.id).then(() => api.processingStatus()).then(setProcessingJobs)}>Retry</button></span>)}{planJobs.filter(job => job.status === "retryable" || job.status === "failed").map(job => <span key={job.id}>Plan job {job.id.slice(0, 8)} is {job.status}. <button className="text-button" onClick={() => void api.retryPlanJob(job.id).then(() => api.planJobs()).then(setPlanJobs)}>Resume/retry</button></span>)}</section>}
      {config ? page === "add" ? <NewItemPage config={config} /> : page === "library" ? <LibraryPage onBuildTrip={ids => { setSelectedIds(ids); window.history.pushState({}, "", "/trips/new"); setPage("trip"); }} onReview={id => { setReviewId(id); setPage("review"); }} /> : page === "trip" ? <TripBuilderPage selectedIds={selectedIds} /> : page === "plan" && routePlanId ? <PlanRoute planId={routePlanId} /> : reviewId ? <main className="library-page"><MetadataReview itemId={reviewId} onReady={() => setPage("library")} onDeleted={() => setPage("library")} /></main> : null : (
        <main className="loading-shell" aria-live="polite">
          <h1>{error ? "Could not reach PackRight" : "Opening PackRight…"}</h1>
          <p>{error ?? "Checking the local API and upload limits."}</p>
        </main>
      )}
    </>
  );
}
