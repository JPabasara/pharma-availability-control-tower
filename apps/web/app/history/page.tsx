"use client";

import { useEffect, useMemo, useState } from "react";

import { getApprovedPlans } from "@/lib/api";
import { formatDateTime, formatInteger } from "@/lib/format";
import type { ApprovedPlan } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";


export default function HistoryPage() {
  const [plans, setPlans] = useState<ApprovedPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const approvedPlans = await getApprovedPlans();
        if (!ignore) {
          setPlans(approvedPlans.approved_plans);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load history.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, []);

  const totalStops = useMemo(
    () => plans.reduce((sum, plan) => sum + plan.stops.length, 0),
    [plans]
  );

  const overrideDecisions = useMemo(
    () =>
      plans.reduce(
        (sum, plan) =>
          sum +
          plan.decisions.filter((decision) => decision.decision_type === "override").length,
        0
      ),
    [plans]
  );

  const rejectDecisions = useMemo(
    () =>
      plans.reduce(
        (sum, plan) =>
          sum +
          plan.decisions.filter((decision) => decision.decision_type === "reject").length,
        0
      ),
    [plans]
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="History"
        description="Immutable approved plans and the decision trail that led to them."
      />

      {loading ? <LoadingPanel label="Loading approved-plan history..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      <div className="metric-grid">
        <MetricCard
          label="Approved Plans"
          value={formatInteger(plans.length)}
          detail="Frozen versions that already affected demo-state."
          accent="teal"
        />
        <MetricCard
          label="Plan Stops"
          value={formatInteger(totalStops)}
          detail="Total stop records represented across approved history."
          accent="ink"
        />
        <MetricCard
          label="Override Decisions"
          value={formatInteger(overrideDecisions)}
          detail="Manual override events preserved in history and reports."
          accent="amber"
        />
        <MetricCard
          label="Rejected Decisions"
          value={formatInteger(rejectDecisions)}
          detail="Rejected decisions preserved in history."
          accent="rose"
        />
      </div>

      {!loading && !plans.length ? (
        <EmptyState
          title="No approved plans yet"
          description="Approve a draft plan from Dispatch and it will appear here as immutable history."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      {plans.length ? (
        <SectionCard
          title="Approved Versions"
          description="Planner-visible view of each approved version, its stops, and its associated decisions."
        >
          <div className="panel-grid">
            {plans.map((plan) => (
              <article key={plan.id} className="report-card">
                <div className="manifest-card-header">
                  <div>
                    <h4>Approved Version #{plan.version_number}</h4>
                    <p>
                      Approved {formatDateTime(plan.approved_at)} by {plan.approved_by ?? "planner"}
                    </p>
                  </div>
                  <StatusPill value="approved" tone="success" />
                </div>

                <div className="detail-list">
                  <span className="detail-chip">Stops {formatInteger(plan.stops.length)}</span>
                  <span className="detail-chip">Score {plan.score ?? 0}</span>
                </div>

                <div className="stack-list" style={{ marginTop: "1rem" }}>
                  {plan.stops.map((stop) => (
                    <div key={`${plan.id}-${stop.stop_sequence}-${stop.lorry_id}`} className="list-card">
                      <h4>
                        Stop {stop.stop_sequence}: {stop.registration}
                      </h4>
                      <p>
                        {stop.dc_name} ({stop.dc_code}) | {stop.lorry_type}
                      </p>
                      <div className="detail-list">
                        {stop.items.map((item) => (
                          <span key={`${stop.stop_sequence}-${item.sku_id}`} className="detail-chip">
                            {item.sku_code}: {formatInteger(item.quantity)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="stack-list" style={{ marginTop: "1rem" }}>
                  {plan.decisions.map((decision) => (
                    <div key={decision.id} className="list-card">
                      <h4>
                        <StatusPill value={decision.decision_type} /> by {decision.decided_by}
                      </h4>
                      <p>{formatDateTime(decision.decided_at)}</p>
                      {decision.notes ? <p>{decision.notes}</p> : null}
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}
