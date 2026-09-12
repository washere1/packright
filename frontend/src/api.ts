import type { AssetUploadResponse, CreateItemDraftRequest, EnrichmentResult, Geometry, HealthResponse, Item, ItemConfirmation, ItemConfirmationRequest, ItemReview, LibraryItem, PackingPlan, PlanExplanation, PreviewRecord, PreviewView, ProcessingJob, PublicConfigResponse, Suitcase, SuitcaseBoundaryRequest, TripItemRequest, TripPreflight, TripSnapshot, TripSummary, ValidationResult, PlanJob } from "./contracts";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new ApiError(response.status, `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

async function postJson<TResponse, TRequest>(path: string, body: TRequest, idempotencyKey?: string): Promise<TResponse> {
  const response = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...(idempotencyKey ? { "X-Idempotency-Key": idempotencyKey } : {}) },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: { message?: string } } | null;
    throw new ApiError(response.status, detail?.detail?.message ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<TResponse>;
}

async function mutateJson<TResponse, TRequest>(method: "PATCH" | "DELETE", path: string, body?: TRequest): Promise<TResponse> {
  const response = await fetch(path, { method, headers: { Accept: "application/json", "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: { message?: string } } | null;
    throw new ApiError(response.status, detail?.detail?.message ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<TResponse>;
}

export function uploadAsset(
  itemId: string,
  file: File,
  onProgress: (loaded: number, total: number | null) => void,
): Promise<AssetUploadResponse> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `/api/items/${itemId}/asset`);
    request.responseType = "json";
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.setRequestHeader("X-Upload-Filename", encodeURIComponent(file.name));
    request.upload.addEventListener("progress", event => onProgress(event.loaded, event.lengthComputable ? event.total : null));
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) resolve(request.response as AssetUploadResponse);
      else reject(new ApiError(request.status, request.response?.detail?.message ?? `Upload failed: ${request.status}`));
    });
    request.addEventListener("error", () => reject(new ApiError(0, "Network error while uploading. Your inputs are still here.")));
    request.addEventListener("abort", () => reject(new ApiError(0, "Upload was cancelled. Your inputs are still here.")));
    request.upload.addEventListener("load", () => onProgress(file.size, file.size));
    request.send(file);
  });
}

export async function uploadPreview(itemId: string, geometryVersion: number, view: PreviewView, image: Blob): Promise<PreviewRecord> {
  const query = new URLSearchParams({ view, geometry_version: String(geometryVersion), renderer_version: "three-r180-v1" });
  const response = await fetch(`/api/items/${itemId}/previews?${query}`, {
    method: "POST", headers: { Accept: "application/json", "Content-Type": image.type }, body: image,
  });
  if (!response.ok) throw new ApiError(response.status, `Preview upload failed: ${response.status}`);
  return response.json() as Promise<PreviewRecord>;
}

export const api = {
  health: () => getJson<HealthResponse>("/api/health"),
  config: () => getJson<PublicConfigResponse>("/api/config"),
  createDraft: (draft: CreateItemDraftRequest) => postJson<Item, CreateItemDraftRequest>("/api/items", draft),
  processItem: (itemId: string, scaleCorrection = 1) => postJson<Geometry, { scale_correction: number }>(`/api/items/${itemId}/process`, { scale_correction: scaleCorrection }),
  enrichItem: (itemId: string) => postJson<EnrichmentResult, Record<string, never>>(`/api/items/${itemId}/enrich`, {}),
  getReview: (itemId: string) => getJson<ItemReview>(`/api/items/${itemId}/review`),
  previews: (itemId: string, geometryVersion?: number) => getJson<PreviewRecord[]>(`/api/items/${itemId}/previews${geometryVersion ? `?geometry_version=${geometryVersion}` : ""}`),
  confirmItem: (itemId: string, request: ItemConfirmationRequest, idempotencyKey?: string) => postJson<ItemConfirmation, ItemConfirmationRequest>(`/api/items/${itemId}/confirm`, request, idempotencyKey),
  updateItem: (itemId: string, request: Partial<Pick<Item, "name" | "weight_g" | "priority_stars">>) => mutateJson<Item, typeof request>("PATCH", `/api/items/${itemId}`, request),
  deleteItem: (itemId: string) => mutateJson<{ deleted: boolean }, never>("DELETE", `/api/items/${itemId}`),
  restoreItem: (itemId: string) => postJson<Item, Record<string, never>>(`/api/items/${itemId}/restore`, {}),
  library: (kind?: "custom" | "stock", search = "", category = "", lifecycle?: "draft" | "ready" | "archived") => getJson<LibraryItem[]>(`/api/library?${new URLSearchParams({ ...(kind ? { kind } : {}), search, ...(category ? { category } : {}), ...(lifecycle ? { lifecycle } : {}) })}`),
  cloneStock: (id: string) => postJson<Item, Record<string, never>>(`/api/stock/${id}/clone`, {}),
  createTrip: (name: string, suitcase: Suitcase, selectedItemIds: string[] = []) => postJson<TripSummary, { name: string; suitcase: Suitcase; selected_item_ids: string[] }>("/api/trips", { name, suitcase, selected_item_ids: selectedItemIds }),
  trips: () => getJson<TripSummary[]>("/api/trips"),
  getTrip: (id: string) => getJson<TripSummary>(`/api/trips/${id}`),
  updateTrip: (id: string, name: string, suitcase: Suitcase) => mutateJson<TripSummary, { name: string; suitcase: Suitcase }>("PATCH", `/api/trips/${id}`, { name, suitcase }),
  setTripItem: (id: string, request: TripItemRequest) => postJson<TripSummary, TripItemRequest>(`/api/trips/${id}/items`, request),
  updateTripItem: (tripId: string, itemId: string, request: Omit<TripItemRequest, "item_id">) => fetchJson<TripSummary>(`/api/trips/${tripId}/items/${itemId}`, "PUT", request),
  removeTripItem: (tripId: string, itemId: string) => fetchJson<TripSummary>(`/api/trips/${tripId}/items/${itemId}`, "DELETE"),
  preflight: (tripId: string) => getJson<TripPreflight>(`/api/trips/${tripId}/preflight`),
  snapshotTrip: (id: string) => postJson<TripSnapshot, Record<string, never>>(`/api/trips/${id}/snapshot`, {}),
  createPlan: (id: string, predecessorPlanId?: string, idempotencyKey?: string) => postJson<PackingPlan, { predecessor_plan_id?: string }>(`/api/trips/${id}/plans`, predecessorPlanId ? { predecessor_plan_id: predecessorPlanId } : {}, idempotencyKey),
  createPlanJob: (id: string, seed = 7, idempotencyKey?: string) => postJson<PlanJob, { seed: number }>(`/api/trips/${id}/plan-jobs`, { seed }, idempotencyKey),
  getPlanJob: (id: string) => getJson<PlanJob>(`/api/plan-jobs/${id}`),
  planJobs: () => getJson<PlanJob[]>("/api/plan-jobs"),
  getPlan: (id: string) => getJson<PackingPlan>(`/api/plans/${id}`),
  retryPlanJob: (id: string) => postJson<PlanJob, Record<string, never>>(`/api/plan-jobs/${id}/retry`, {}),
  planInstructions: (id: string) => getJson<PlanExplanation>(`/api/plans/${id}/instructions`),
  validatePlan: (id: string) => postJson<ValidationResult, Record<string, never>>(`/api/plans/${id}/validate`, {}),
  replan: (id: string, suitcase?: Suitcase, name?: string, idempotencyKey?: string) => postJson<PackingPlan, { suitcase?: Suitcase; name?: string }>(`/api/plans/${id}/replan`, { ...(suitcase ? { suitcase } : {}), ...(name ? { name } : {}) }, idempotencyKey),
  replanJob: (id: string, suitcase?: Suitcase, name?: string, idempotencyKey?: string) => postJson<PlanJob, { suitcase?: Suitcase; name?: string }>(`/api/plans/${id}/replan-jobs`, { ...(suitcase ? { suitcase } : {}), ...(name ? { name } : {}) }, idempotencyKey),
  processingStatus: () => getJson<ProcessingJob[]>("/api/processing/status"),
  retryProcessing: (id: string) => postJson<ProcessingJob, Record<string, never>>(`/api/processing/${id}/retry`, {}),
  seedDemo: () => postJson<{ trip_id: string; item_ids: string[] }, Record<string, never>>("/api/operations/demo/seed", {}),
  resetDemo: () => postJson<{ removed_records: number }, Record<string, never>>("/api/operations/demo/reset", {}),
  suitcases: () => getJson<Suitcase[]>("/api/suitcases"),
  createSuitcase: (request: SuitcaseBoundaryRequest) => postJson<Suitcase, SuitcaseBoundaryRequest>("/api/suitcases", request),
  updateSuitcasePreset: (id: string, request: SuitcaseBoundaryRequest) => mutateJson<Suitcase, SuitcaseBoundaryRequest>("PATCH", `/api/suitcases/${id}`, request),
  deleteSuitcasePreset: (id: string) => mutateJson<{ deleted: boolean }, never>("DELETE", `/api/suitcases/${id}`),
};

async function fetchJson<TResponse>(path: string, method: "PUT" | "DELETE", body?: unknown): Promise<TResponse> {
  const response = await fetch(path, { method, headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: { message?: string } } | null;
    throw new ApiError(response.status, detail?.detail?.message ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<TResponse>;
}
