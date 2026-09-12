export type WeightUnit = "g" | "kg" | "oz" | "lb";
export type LengthUnit = "mm" | "cm" | "in";
export type ItemStage = "draft" | "uploaded" | "processing" | "awaiting_review" | "ready" | "failed";
export type ProgressStage = "none" | "upload" | "geometry" | "previews" | "enrichment" | "complete";
export type PlanState = "queued" | "solving" | "validating" | "feasible" | "infeasible" | "search_exhausted" | "failed";
export type OrientationId = "xyz" | "xzy" | "yxz" | "yzx" | "zxy" | "zyx";

export interface DimensionsMm { width: number; height: number; depth: number }
export interface Matrix3 { values: [[number, number, number], [number, number, number], [number, number, number]] }
export interface Orientation { id: OrientationId; matrix: Matrix3 }

export interface ItemDraft {
  id: string;
  name: string | null;
  weight_g: number;
  priority_stars: 1 | 2 | 3 | 4 | 5;
  display_weight_unit: WeightUnit;
}

export interface Geometry {
  version: number;
  asset_id: string;
  units: "mm";
  aabb_mm: { minimum: [number, number, number]; maximum: [number, number, number] };
  canonical_dimensions_mm: DimensionsMm;
  geometric_center_mm: [number, number, number];
  source_to_canonical: number[];
  canonical_to_source: number[];
  box_volume_mm3: number;
  mesh_volume_mm3: number | null;
  fill_ratio: number | null;
  clearance_mm: DimensionsMm;
  preview_camera_distance_mm: number;
  scale_correction: number;
  requires_scale_confirmation: boolean;
  mesh_watertight: boolean;
  orientations: Orientation[];
  warnings: string[];
}

export interface Handling {
  version: number;
  category: string;
  fragility: "low" | "medium" | "high";
  compressibility: "none" | "light" | "high";
  stack_class: "base" | "neutral" | "top_only";
  can_support_weight: boolean;
  liquid_risk: boolean;
  legal_orientations: OrientationId[];
  access: "buried_ok" | "normal" | "quick";
  confidence: ConfidenceScores;
  provenance: string;
  short_reason: string;
  needs_confirmation: string[];
}

export type HandlingEdit = Pick<Handling, "category" | "fragility" | "compressibility" | "stack_class" | "can_support_weight" | "liquid_risk" | "legal_orientations" | "access">;
export interface ItemConfirmationRequest { name: string; weight_g: number; priority_stars: 1 | 2 | 3 | 4 | 5; handling: HandlingEdit; acknowledge_scale: boolean }
export interface ItemConfirmation {
  id: string; item_id: string; version: number; generated_handling: Handling; confirmed_handling: Handling;
  confirmed_name: string; confirmed_weight_g: number; confirmed_priority_stars: number; scale_acknowledged: boolean; confirmed_at: string;
}
export interface ItemReview { item: Item; latest_confirmation: ItemConfirmation | null; questions: string[] }

export interface ConfidenceScores {
  name: number; category: number; fragility: number; compressibility: number;
  stack_class: number; orientations: number; access: number;
}

export interface EnrichmentSuggestion {
  name: string;
  category: string;
  fragility: "low" | "medium" | "high";
  compressibility: "none" | "light" | "high";
  stack_class: "base" | "neutral" | "top_only";
  can_support_weight: boolean;
  liquid_risk: boolean;
  allowed_orientations: OrientationId[];
  access: "buried_ok" | "normal" | "quick";
  short_reason: string;
  needs_confirmation: string[];
  confidence: ConfidenceScores;
}

export interface EnrichmentResult {
  suggestion: EnrichmentSuggestion;
  provider: string;
  model_id: string;
  prompt_version: string;
  fallback_reason: string | null;
  cached: boolean;
}

export type PreviewView = "front" | "side" | "top" | "three_quarter" | "thumbnail";
export interface PreviewRecord {
  id: string; item_id: string; asset_id: string; geometry_version: number;
  view: PreviewView; renderer_version: string; mime_type: "image/png" | "image/webp";
  byte_size: number; width: number; height: number; storage_path: string; created_at: string;
}

export interface Item extends ItemDraft {
  stage: ItemStage;
  asset_id: string | null;
  geometry: Geometry | null;
  handling: Handling | null;
  error_code: string | null;
  progress_stage: ProgressStage;
}

export interface Suitcase {
  id: string;
  name: string;
  internal_dimensions_mm: DimensionsMm;
  empty_weight_g: number;
  baggage_limit_g: number;
  clearance_mm: number;
  display_length_unit: LengthUnit;
  display_weight_unit: WeightUnit;
}

export interface ItemInstance {
  id: string;
  item_id: string;
  copy_number: number;
  priority_stars: 1 | 2 | 3 | 4 | 5;
  must_pack: boolean; access_preference: "buried_ok" | "normal" | "quick" | null;
}

export interface TripItem { item_id: string; instances: ItemInstance[] }
export interface Trip { id: string; name: string; suitcase: Suitcase; items: TripItem[] }

export interface LibraryItem {
  id: string; kind: "custom" | "stock"; name: string; category: string; dimensions_mm: DimensionsMm | null;
  weight_g: number; priority_stars: 1 | 2 | 3 | 4 | 5; handling: HandlingEdit | null;
  ready: boolean; example_values: boolean; thumbnail_id: string | null; review_route: string | null; asset_id: string | null;
  lifecycle: "draft" | "ready" | "archived"; archived: boolean;
  geometry: Geometry | null;
}
export interface TripItemRequest { item_id: string; quantity: number; priority_stars: 1 | 2 | 3 | 4 | 5; must_pack: boolean; access_preference?: "buried_ok" | "normal" | "quick" | null }
export interface TripSummary { trip: Trip; requested_item_weight_g: number; available_item_weight_g: number; total_utility: number; warnings: string[] }
export interface TripPreflight { requested_instances: number; requested_weight_g: number; padded_volume_mm3: number; baggage_remaining_g: number; missing_metadata: string[]; oversize_instances: string[]; mandatory_contradictions: string[]; actionable_messages: string[] }
export interface SnapshotBox { instance_id: string; item_id: string; copy_number: number; priority_stars: number; must_pack: boolean; effective_padded_dimensions_mm: DimensionsMm; weight_g: number; geometry_version: number; handling_version: number; legal_orientations: OrientationId[] }
export interface TripSnapshot { id: string; trip_id: string; version: number; trip: Trip; item_snapshots: LibraryItem[]; created_at: string; expanded_boxes: SnapshotBox[]; geometry_version: string; handling_confirmation_version: string; solver_version: string; seed: number }

export interface Placement {
  instance_id: string;
  item_id: string;
  position_mm: [number, number, number];
  dimensions_mm: DimensionsMm;
  orientation_id: OrientationId;
  orientation_matrix: Matrix3;
  packing_order: number;
  support_ratio: number;
}

export interface ValidationViolation {
  code: string;
  message: string;
  instance_ids: string[];
  measured_value: number | null;
}

export interface PlanMetrics {
  packed_weight_g: number;
  remaining_allowance_g: number;
  utilization: number;
  retained_utility: number;
  center_of_mass_mm: [number, number, number] | null;
}

export interface ValidationResult {
  validator_version: string;
  valid: boolean;
  violations: ValidationViolation[];
  metrics: PlanMetrics | null;
  validated_at: string;
}

export interface PackingInstruction {
  number: number;
  instance_id: string;
  item_name: string;
  copy_number: number;
  destination: string;
  orientation_label: string;
  handling_note: string | null;
}
export interface PlanExplanation {
  instructions: PackingInstruction[];
  exclusions: string[];
  balance_note: string;
}
export interface ProcessingJob { id: string; item_id: string; stage: ProgressStage; status: "running" | "completed" | "failed" | "retryable"; error_code: string | null; request_key: string | null; updated_at: string; operation_type: string; requested_scale_correction: number | null; renderer_version: string | null; required_previews: PreviewView[]; retry_count: number; stable_input_reference: string | null }
export type PlanJobState = "queued" | "running" | "completed" | "failed" | "retryable";
export interface PlanJob { id: string; trip_id: string; snapshot_id: string; kind: "plan" | "replan"; status: PlanJobState; progress_stage: string; plan_id: string | null; predecessor_plan_id: string | null; error_code: string | null; error_message: string | null; idempotency_key: string | null; request_hash: string | null; seed: number; created_at: string; updated_at: string }

export interface BaselineDiagnostic {
  name: "lowest_star_first" | "heaviest_first";
  state: "feasible" | "spatial_failure" | "budget_exhausted";
  retained_utility: number | null;
}

export interface SolverDiagnostics {
  selection_mode: "exact" | "bounded_beam";
  heuristic: boolean;
  candidate_subsets: number;
  placement_attempts: number;
  complete_layouts: number;
  validator_rejections: number;
  budget_seconds: number;
  baselines: BaselineDiagnostic[];
}

export interface PackingPlan {
  id: string;
  trip_id: string;
  state: PlanState;
  placements: Placement[];
  excluded_instance_ids: string[];
  validation: ValidationResult | null;
  solver_version: string;
  seed: number;
  runtime_ms: number;
  input_snapshot_version: number;
  snapshot_id: string | null;
  snapshot: TripSnapshot | null;
  predecessor_plan_id: string | null;
  exclusion_evidence: Array<{ instance_id: string; code: string; detail: string }>;
  instructions: PackingInstruction[];
  diagnostics: SolverDiagnostics | null;
}

export interface SuitcaseBoundaryRequest { name: string; width: number; height: number; depth: number; length_unit: LengthUnit; empty_weight: number; baggage_limit: number; weight_unit: WeightUnit; clearance_mm: number }

export interface Limits {
  max_upload_bytes: number;
  max_item_weight_g: number;
  max_dimension_mm: number;
  max_trip_instances: number;
  processing_timeout_seconds: number;
  parser_memory_limit_mb: number;
  max_glb_json_bytes: number;
  max_scene_nodes: number;
  max_decoded_vertices: number;
  max_decoded_faces: number;
  max_preview_bytes: number;
  max_preview_dimension_px: number;
  model_timeout_seconds: number;
  solver_budget_seconds: number;
  max_suitcase_clearance_mm: number;
}

export interface HealthResponse { status: string; service: string; api_version: string }
export interface CreateItemDraftRequest {
  weight_g: number;
  priority_stars: 1 | 2 | 3 | 4 | 5;
  display_weight_unit: WeightUnit;
}
export interface AssetUploadResponse {
  item_id: string;
  asset_id: string;
  stage: "processing";
  progress_stage: "geometry";
  received_bytes: number;
  sha256: string;
  bounds: { minimum_m: [number, number, number]; maximum_m: [number, number, number] };
  vertex_count: number;
  face_count: number;
  mesh_instance_count: number;
  warnings: string[];
}
export interface PublicConfigResponse {
  capabilities: {
    preview_supported: boolean;
    live_enrichment_configured: boolean;
    neutral_enrichment_fallback: boolean;
  };
  limits: Limits;
  units: Record<string, string>;
  coordinates: Record<string, string>;
}
