"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getM2Requests } from "@/lib/api";
import { buildQueryString, formatDateTime, formatInteger } from "@/lib/format";
import { usePlannerRunContext, useResolvedRunId } from "@/lib/run-context";
import type { M2RequestsResponse } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

function RequestsPageContent() {
  const { runContext } = usePlannerRunContext();
  const { runId, loading: runLoading, error: runError } = useResolvedRunId("m2");
  const [data, setData] = useState<M2RequestsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load(activeRunId: number) {
      setLoading(true);
      setError(null);
      try {
        const response = await getM2Requests(activeRunId);
        if (!ignore) {
          setData(response);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load M2 requests.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    if (runId) {
      void load(runId);
    } else {
      setData(null);
    }

    return () => {
      ignore = true;
    };
  }, [runId]);

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
        title="M2 Requests"
        description="Generated DC replenishment requests, urgency bands, and required-by timing."
        actions={
          <div className="page-actions">
            <Link
              href={`/dispatch${buildQueryString(runContext)}`}
              className="button button-secondary"
            >
              Back to Dispatch
            </Link>
          </div>
        }
      />

      {runLoading || loading ? <LoadingPanel label="Loading M2 requests..." /> : null}
      {runError ? <div className="notice notice-error"><p>{runError}</p></div> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {!runLoading && !runId ? (
        <EmptyState
          title="No active M2 run found"
          description="Generate a plan from Dispatch to create replenishment requests for the DC network."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      {data ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Active Run"
              value={`#${data.run_id}`}
              detail="Resolved using the planner run-context priority order."
              accent="ink"
            />
            <MetricCard
              label="Requests"
              value={formatInteger(data.total_requests)}
              detail={`${formatInteger(impactedDcs)} DCs are represented in this run.`}
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
              detail="Total requested quantity across all generated replenishment lines."
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
            description="All replenishment requests produced by M2 for the active run."
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
    <Suspense fallback={<LoadingPanel label="Loading M2 requests..." />}>
      <RequestsPageContent />
    </Suspense>
  );
}
