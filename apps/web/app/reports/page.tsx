"use client";

import { useEffect, useMemo, useState } from "react";

import { getApprovedPlans, getAuditTrail } from "@/lib/api";
import { downloadText, formatDateTime, formatInteger, rowsToCsv } from "@/lib/format";
import { generateDispatchPlanPdf } from "@/lib/pdf";
import type { ApprovedPlan, AuditEntry } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

export default function ReportsPage() {
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [plans, setPlans] = useState<ApprovedPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [auditTrail, approvedPlans] = await Promise.all([
          getAuditTrail(100),
          getApprovedPlans(),
        ]);
        if (!ignore) {
          setAudit(auditTrail.audit_trail);
          setPlans(approvedPlans.approved_plans);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load reports.");
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

  /* ── Derived metrics ── */
  const totalStops = useMemo(
    () => plans.reduce((sum, p) => sum + p.stops.length, 0),
    [plans]
  );

  const totalUnitsDispatched = useMemo(
    () =>
      plans.reduce(
        (sum, p) =>
          sum + p.stops.reduce((a, s) => a + s.items.reduce((b, i) => b + i.quantity, 0), 0),
        0
      ),
    [plans]
  );

  const overrideCount = useMemo(
    () =>
      plans.reduce(
        (sum, p) =>
          sum + p.decisions.filter((d) => d.decision_type === "override").length,
        0
      ),
    [plans]
  );

  /* ── Handlers ── */
  function exportAuditTrailCsv() {
    const csv = rowsToCsv(
      ["id", "entity_type", "entity_id", "action", "actor", "timestamp", "details"],
      audit.map((entry) => [
        entry.id,
        entry.entity_type,
        entry.entity_id,
        entry.action,
        entry.actor,
        entry.timestamp ?? "",
        JSON.stringify(entry.details ?? {}),
      ])
    );
    downloadText("audit-trail.csv", csv, "text/csv;charset=utf-8");
  }

  function handleDownloadPdf() {
    if (!selectedPlanId) return;
    const plan = plans.find((p) => p.id === selectedPlanId);
    if (!plan) return;
    setGenerating(true);
    setTimeout(() => {
      generateDispatchPlanPdf(plan);
      setGenerating(false);
    }, 100);
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Reports"
        description="Export audit trails and download structured dispatch plan PDFs for HEMAS Pharmacy Distribution."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={exportAuditTrailCsv}
              disabled={!audit.length}
            >
              Export Audit Trail CSV
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={handleDownloadPdf}
              disabled={!selectedPlanId || generating}
            >
              {generating ? "Generating PDF…" : "Download Plan PDF"}
            </button>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading report data..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {/* ── 4 Metric Cards ── */}
      <div className="metric-grid">
        <MetricCard
          label="Approved Plans"
          value={formatInteger(plans.length)}
          detail="Total dispatch plans approved and ready for PDF export."
          accent="teal"
        />
        <MetricCard
          label="Total Units Dispatched"
          value={formatInteger(totalUnitsDispatched)}
          detail="Aggregate quantity across all approved plan stops."
          accent="primary"
        />
        <MetricCard
          label="Override Decisions"
          value={formatInteger(overrideCount)}
          detail="Manual planner overrides recorded across all versions."
          accent="amber"
        />
        <MetricCard
          label="Audit Entries"
          value={formatInteger(audit.length)}
          detail="Available for CSV export with the current filters."
          accent="rose"
        />
      </div>

      {/* ── Empty state ── */}
      {!loading && !plans.length && !audit.length ? (
        <EmptyState
          title="Nothing to report yet"
          description="Generate and approve a dispatch plan to see it here for PDF download."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      {/* ── Approved / Overridden Dispatch Plan summary list ── */}
      {plans.length > 0 ? (
        <SectionCard
          title="Dispatch Plan Archive"
          description="Select an approved or overridden dispatch plan, then use the button above to download its PDF."
        >
          <div className="plan-archive-list">
            {plans.map((plan) => {
              const isSelected = selectedPlanId === plan.id;
              const hasOverride = plan.decisions.some(
                (d) => d.decision_type === "override"
              );
              const planQty = plan.stops.reduce(
                (a, s) => a + s.items.reduce((b, i) => b + i.quantity, 0),
                0
              );
              const dcCount = new Set(plan.stops.map((s) => s.dc_code)).size;

              return (
                <button
                  key={plan.id}
                  type="button"
                  className={`plan-archive-card${isSelected ? " plan-archive-card-selected" : ""}`}
                  onClick={() => setSelectedPlanId(isSelected ? null : plan.id)}
                >
                  <div className="plan-archive-card-left">
                    <div className="plan-archive-radio">
                      <span
                        className={`plan-archive-dot${isSelected ? " plan-archive-dot-active" : ""}`}
                      />
                    </div>
                    <div className="plan-archive-info">
                      <h4>
                        Plan Version #{plan.version_number}
                        {hasOverride ? (
                          <StatusPill value="overridden" tone="warning" />
                        ) : (
                          <StatusPill value="approved" tone="success" />
                        )}
                      </h4>
                      <p>
                        Approved {formatDateTime(plan.approved_at)} by{" "}
                        {plan.approved_by ?? "Planner"}
                      </p>
                    </div>
                  </div>
                  <div className="plan-archive-stats">
                    <span className="detail-chip">{plan.runs.length} Runs</span>
                    <span className="detail-chip">{plan.stops.length} Stops</span>
                    <span className="detail-chip">{dcCount} DCs</span>
                    <span className="detail-chip">{planQty.toLocaleString()} Units</span>
                    <span className="detail-chip">Score {plan.score ?? "—"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </SectionCard>
      ) : null}

      {/* ── Audit Trail Table ── */}
      <SectionCard
        title="Audit Trail"
        description="Recent audit events with export-ready detail payloads."
      >
        <DataTable
          columns={[
            {
              key: "entity",
              header: "Entity",
              render: (row: AuditEntry) => `${row.entity_type} #${row.entity_id}`,
            },
            {
              key: "action",
              header: "Action",
              render: (row: AuditEntry) => <StatusPill value={row.action} />,
            },
            { key: "actor", header: "Actor", render: (row: AuditEntry) => row.actor },
            {
              key: "time",
              header: "Timestamp",
              render: (row: AuditEntry) => formatDateTime(row.timestamp),
            },
            {
              key: "details",
              header: "Details",
              render: (row: AuditEntry) => JSON.stringify(row.details ?? {}),
              className: "mono",
            },
          ]}
          rows={audit}
          getRowKey={(row: AuditEntry) => row.id}
          emptyText="No audit entries are available for reporting yet."
        />
      </SectionCard>
    </div>
  );
}
