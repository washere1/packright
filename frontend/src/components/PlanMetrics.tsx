import type { PackingPlan } from "../contracts";

export function PlanMetrics({ plan }: { plan: PackingPlan }) {
  const metrics = plan.validation?.metrics;
  return <div className="trip-metrics plan-metrics"><div><small>Weight</small><strong>{metrics ? `${metrics.packed_weight_g.toLocaleString()} g` : "—"}</strong></div><div><small>Utilization</small><strong>{metrics ? `${(metrics.utilization * 100).toFixed(1)}%` : "—"}</strong></div><div><small>Priority retained</small><strong>{metrics?.retained_utility ?? "—"}</strong></div><div><small>Remaining allowance</small><strong>{metrics ? `${metrics.remaining_allowance_g.toLocaleString()} g` : "—"}</strong></div></div>;
}

