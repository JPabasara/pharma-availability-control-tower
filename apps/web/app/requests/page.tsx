"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, getCurrentM2Requests, refreshM2 } from "@/lib/api";
import { formatDate, formatDateTime, formatInteger } from "@/lib/format";
import type { M2RequestsResponse } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

type Notice = { tone: "success" | "error"; message: string };

function RequestsPageContent() {
  const [data, setData] = useState<M2RequestsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function loadCurrent() {
    setLoading(true);
    setError(null);
    try {
      const response = await getCurrentM2Requests();
      setData(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load Forecaster requests.");
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
      await refreshM2();
      await loadCurrent();
      setNotice({ tone: "success", message: "Forecaster was refreshed successfully." });
    } catch (cause) {
      const message =
        cause instanceof ApiError
          ? cause.message
          : cause instanceof Error
            ? cause.message
            : "Unable to refresh Forecaster.";
      setNotice({ tone: "error", message });
    } finally {
      setActionLoading(false);
    }
  }

  const totalRequestedUnits = useMemo(
    () => data?.requests.reduce((sum, request) => sum + request.requested_quantity, 0) ?? 0,
    [data]
  );
  const criticalCount = useMemo(
    () => data?.requests.filter((request) => request.urgency === "critical").length ?? 0,
    [data]
  );
  const impactedDcs = useMemo(
    () => new Set(data?.requests.map((request) => request.dc_id) ?? []).size,
    [data]
  );
  const urgencyGroups = useMemo(() => {
    const groups = new Map<string, number>();
    (data?.requests ?? []).forEach((request) => {
      groups.set(request.urgency, (groups.get(request.urgency) ?? 0) + 1);
    });
    return Array.from(groups.entries());
  }, [data]);

  return (
    <div className="page-stack">
      <PageHeader
        title="Forecaster"
        description="Generated DC replenishment requests, urgency bands, and required-by timing."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => void handleRefresh()}
              disabled={loading || actionLoading}
            >
              {actionLoading ? "..." : "Refresh Forecaster"}
            </button>
            <Link href="/dispatch" className="button button-secondary">
              Back to Dispatch
            </Link>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading Forecaster requests..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}
      {notice ? (
        <div className={`notice notice-${notice.tone}`}>
          <p>{notice.message}</p>
        </div>
      ) : null}

      {!loading && !data?.available ? (
        <EmptyState
          title="No live Forecaster snapshot yet"
          description="Use Refresh Forecaster to regenerate the latest replenishment requests for the DC network."
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
                  : "Current Forecaster snapshot."
              }
              accent="ink"
            />
            <MetricCard
              label="Requests"
              value={formatInteger(data.total_requests)}
              detail={`${formatInteger(impactedDcs)} DCs are represented in this snapshot.`}
              accent="teal"
            />
            <MetricCard
              label="Critical Requests"
              value={formatInteger(criticalCount)}
              detail="These shortage signals should dominate dispatch decisions."
              accent="rose"
            />
            <MetricCard
              label="Requested Units"
              value={formatInteger(totalRequestedUnits)}
              detail="Total requested quantity across the latest Forecaster snapshot."
              accent="amber"
            />
          </div>

          <SectionCard
            title="Urgency Mix"
            description="A quick view of the generated request pressure before reviewing the full table."
          >
            <div className="cards-grid">
              {urgencyGroups.map(([urgency, count]) => (
                <div key={urgency} className="list-card">
                  <h4>
                    <StatusPill value={urgency} />
                  </h4>
                  <p>{formatInteger(count)} request lines in this urgency band.</p>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="Request Lines"
            description="All replenishment requests produced by the latest Forecaster snapshot."
          >
            <DataTable
              columns={[
                { key: "dc", header: "DC", render: (row) => `${row.dc_code} - ${row.dc_name}` },
                { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                { key: "qty", header: "Requested", render: (row) => formatInteger(row.requested_quantity) },
                { key: "urgency", header: "Urgency", render: (row) => <StatusPill value={row.urgency} /> },
                { key: "requiredBy", header: "Required By", render: (row) => formatDateTime(row.required_by) },
              ]}
              rows={data.requests}
              getRowKey={(row) => row.id}
            />
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}

export default function RequestsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading Forecaster requests..." />}>
      <RequestsPageContent />
    </Suspense>
  );
}
