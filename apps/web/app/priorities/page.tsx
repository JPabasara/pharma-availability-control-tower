"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, getCurrentM1Results, refreshM1 } from "@/lib/api";
import { formatDate, formatDateTime, formatInteger, formatNumber } from "@/lib/format";
import type { M1ResultsResponse } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

type Notice = { tone: "success" | "error"; message: string };

function PrioritiesPageContent() {
  const [data, setData] = useState<M1ResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function loadCurrent() {
    setLoading(true);
    setError(null);
    try {
      const response = await getCurrentM1Results();
      setData(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load M1 results.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCurrent();
  }, []);

  async function handleRefresh() {
    setActionLoading(true);
    setNotice(null);
    try {
      await refreshM1();
      await loadCurrent();
      setNotice({ tone: "success", message: "M2 and M1 were refreshed successfully." });
    } catch (cause) {
      const message =
        cause instanceof ApiError
          ? cause.message
          : cause instanceof Error
            ? cause.message
            : "Unable to refresh M1.";
      setNotice({ tone: "error", message });
    } finally {
      setActionLoading(false);
    }
  }

  const criticalLines = useMemo(
    () => data?.line_results.filter((line) => line.priority_band === "critical").length ?? 0,
    [data]
  );
  const reeferLines = useMemo(
    () => data?.line_results.filter((line) => line.reefer_required).length ?? 0,
    [data]
  );
  const topScore = useMemo(() => data?.line_results[0]?.priority_score ?? 0, [data]);

  return (
    <div className="page-stack">
      <PageHeader
        title="M1 Priorities"
        description="Shipment-line priority scores and the aggregated SKU view for planner review."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => void handleRefresh()}
              disabled={loading || actionLoading}
            >
              {actionLoading ? "..." : "Refresh M1"}
            </button>
            <Link href="/dispatch" className="button button-secondary">
              Back to Dispatch
            </Link>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading M1 priorities..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}
      {notice ? (
        <div className={`notice notice-${notice.tone}`}>
          <p>{notice.message}</p>
        </div>
      ) : null}

      {!loading && !data?.available ? (
        <EmptyState
          title="No live M1 snapshot yet"
          description="Use Refresh M1 to regenerate M2 and M1, then review the latest singleton priority results here."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      {data?.available ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Last Refreshed"
              value={data.generated_at ? formatDateTime(data.generated_at) : "Not yet"}
              detail={
                data.planning_start_date
                  ? `Planning Day 1 starts on ${formatDate(data.planning_start_date)}.`
                  : "Current singleton M1 snapshot."
              }
              accent="ink"
            />
            <MetricCard
              label="Line Results"
              value={formatInteger(data.total_lines)}
              detail="Manifest lines scored by the latest M1 run."
              accent="teal"
            />
            <MetricCard
              label="Critical Lines"
              value={formatInteger(criticalLines)}
              detail="Highest urgency lines requiring planner attention first."
              accent="rose"
            />
            <MetricCard
              label="Top Score"
              value={formatNumber(topScore)}
              detail={`${formatInteger(reeferLines)} reefer-sensitive lines are in this snapshot.`}
              accent="amber"
            />
          </div>

          <SectionCard
            title="Aggregated SKU Summary"
            description="Highest band and score distribution collapsed to the SKU level."
          >
            <DataTable
              columns={[
                { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                { key: "band", header: "Highest Band", render: (row) => <StatusPill value={row.highest_band} /> },
                { key: "max", header: "Max Score", render: (row) => formatNumber(row.max_score) },
                { key: "avg", header: "Average Score", render: (row) => formatNumber(row.avg_score) },
                { key: "lines", header: "Lines", render: (row) => formatInteger(row.line_count) },
                {
                  key: "reefer",
                  header: "Cold Chain",
                  render: (row) =>
                    row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal",
                },
              ]}
              rows={data.sku_summary}
              getRowKey={(row) => row.sku_id}
            />
          </SectionCard>

          <SectionCard
            title="Line-Level Results"
            description="The planner-facing view of every manifest line scored by the latest M1 snapshot."
          >
            <DataTable
              columns={[
                { key: "manifest", header: "Manifest Line", render: (row) => `#${row.manifest_line_id}` },
                { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                { key: "score", header: "Score", render: (row) => formatNumber(row.priority_score) },
                { key: "band", header: "Band", render: (row) => <StatusPill value={row.priority_band} /> },
                {
                  key: "reefer",
                  header: "Cold Chain",
                  render: (row) =>
                    row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal",
                },
              ]}
              rows={data.line_results}
              getRowKey={(row) => row.id}
            />
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}

export default function PrioritiesPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading M1 priorities..." />}>
      <PrioritiesPageContent />
    </Suspense>
  );
}
