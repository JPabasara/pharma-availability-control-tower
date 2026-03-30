"use client";

import { useEffect, useState } from "react";

import { getApprovedPlans, getAuditTrail } from "@/lib/api";
import { downloadText, formatDateTime, formatInteger, rowsToCsv } from "@/lib/format";
import type { ApprovedPlan, AuditEntry } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

export default function ReportsPage() {
  const [plans, setPlans] = useState<ApprovedPlan[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [approvedPlans, auditTrail] = await Promise.all([
          getApprovedPlans(),
          getAuditTrail(100),
        ]);
        if (!ignore) {
          setPlans(approvedPlans.approved_plans);
          setAudit(auditTrail.audit_trail);
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

  function exportApprovedPlansJson() {
    downloadText("approved-plans.json", JSON.stringify(plans, null, 2), "application/json;charset=utf-8");
  }

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

  return (
    <div className="page-stack">
      <PageHeader
        title="Reports"
        description="Planner-facing reporting and lightweight client-side exports from approved plans and audit data."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={exportApprovedPlansJson}
              disabled={!plans.length}
            >
              Export Approved Plans JSON
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={exportAuditTrailCsv}
              disabled={!audit.length}
            >
              Export Audit Trail CSV
            </button>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading report data..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      <div className="metric-grid">
        <MetricCard
          label="Approved Plans"
          value={formatInteger(plans.length)}
          detail="Available for JSON export directly from the browser."
          accent="teal"
        />
        <MetricCard
          label="Audit Entries"
          value={formatInteger(audit.length)}
          detail="Available for CSV export with the current filters."
          accent="ink"
        />
        <MetricCard
          label="Latest Approval"
          value={plans[0]?.approved_at ? formatDateTime(plans[0].approved_at) : "None"}
          detail="Most recent approved version in report history."
          accent="amber"
        />
        <MetricCard
          label="Export Readiness"
          value={plans.length || audit.length ? "Ready" : "Waiting"}
          detail="Exports activate as soon as there is approved or audited data."
          accent="rose"
        />
      </div>

      {!loading && !plans.length && !audit.length ? (
        <EmptyState
          title="Nothing to report yet"
          description="Approve plans and generate audit events from the planner workflow to populate the report surfaces."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      <SectionCard
        title="Approved Plans Snapshot"
        description="Compact reporting view of approved versions and their planner decisions."
      >
        <DataTable
          columns={[
            { key: "version", header: "Version", render: (row) => `#${row.version_number}` },
            { key: "run", header: "Engine Run", render: (row) => `#${row.engine_run_id}` },
            { key: "score", header: "Score", render: (row) => row.score ?? 0 },
            { key: "approved", header: "Approved At", render: (row) => formatDateTime(row.approved_at) },
            { key: "by", header: "Approved By", render: (row) => row.approved_by ?? "planner" },
            { key: "decisions", header: "Decisions", render: (row) => formatInteger(row.decisions.length) },
          ]}
          rows={plans}
          getRowKey={(row) => row.id}
          emptyText="No approved plans are available for reporting yet."
        />
      </SectionCard>

      <SectionCard
        title="Audit Trail Snapshot"
        description="Recent audit events with export-ready detail payloads."
      >
        <DataTable
          columns={[
            { key: "entity", header: "Entity", render: (row) => `${row.entity_type} #${row.entity_id}` },
            { key: "action", header: "Action", render: (row) => <StatusPill value={row.action} /> },
            { key: "actor", header: "Actor", render: (row) => row.actor },
            { key: "time", header: "Timestamp", render: (row) => formatDateTime(row.timestamp) },
            {
              key: "details",
              header: "Details",
              render: (row) => JSON.stringify(row.details ?? {}),
              className: "mono",
            },
          ]}
          rows={audit}
          getRowKey={(row) => row.id}
          emptyText="No audit entries are available for reporting yet."
        />
      </SectionCard>
    </div>
  );
}
