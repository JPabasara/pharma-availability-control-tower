"use client";

import { useEffect, useState } from "react";

import { getApprovedPlans, getAuditTrail } from "@/lib/api";
import { downloadText, formatDateTime, formatInteger, rowsToCsv } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

export default function ReportsPage() {
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const auditTrail = await getAuditTrail(100);
        if (!ignore) {
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
        description="Planner-facing reporting and lightweight client-side exports from audit data."
        actions={
          <div className="page-actions">
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
          label="Audit Entries"
          value={formatInteger(audit.length)}
          detail="Available for CSV export with the current filters."
          accent="ink"
        />
        <MetricCard
          label="Export Readiness"
          value={audit.length ? "Ready" : "Waiting"}
          detail="Export activates as soon as there is audited data."
          accent="rose"
        />
      </div>

      {!loading && !audit.length ? (
        <EmptyState
          title="Nothing to report yet"
          description="Generate audit events from the planner workflow to populate the report surfaces."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      <SectionCard
        title="Audit Trail"
        description="Recent audit events with export-ready detail payloads."
      >
        <DataTable
          columns={[
            { key: "entity", header: "Entity", render: (row: AuditEntry) => `${row.entity_type} #${row.entity_id}` },
            { key: "action", header: "Action", render: (row: AuditEntry) => <StatusPill value={row.action} /> },
            { key: "actor", header: "Actor", render: (row: AuditEntry) => row.actor },
            { key: "time", header: "Timestamp", render: (row: AuditEntry) => formatDateTime(row.timestamp) },
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
