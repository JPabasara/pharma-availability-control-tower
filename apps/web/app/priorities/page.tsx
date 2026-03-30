"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { getM1Results } from "@/lib/api";
import { buildQueryString, formatInteger, formatNumber } from "@/lib/format";
import { usePlannerRunContext, useResolvedRunId } from "@/lib/run-context";
import type { M1ResultsResponse } from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

function PrioritiesPageContent() {
  const { runContext } = usePlannerRunContext();
  const { runId, loading: runLoading, error: runError } = useResolvedRunId("m1");
  const [data, setData] = useState<M1ResultsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load(activeRunId: number) {
      setLoading(true);
      setError(null);
      try {
        const response = await getM1Results(activeRunId);
        if (!ignore) {
          setData(response);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load M1 results.");
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

  const criticalLines = useMemo(
    () => data?.line_results.filter((line) => line.priority_band === "critical").length ?? 0,
    [data]
  );

  const reeferLines = useMemo(
    () => data?.line_results.filter((line) => line.reefer_required).length ?? 0,
    [data]
  );

  const topScore = useMemo(
    () => data?.line_results[0]?.priority_score ?? 0,
    [data]
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="M1 Priorities"
        description="Shipment-line priority scores and the aggregated SKU view for planner review."
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

      {runLoading || loading ? <LoadingPanel label="Loading M1 priorities..." /> : null}
      {runError ? <div className="notice notice-error"><p>{runError}</p></div> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {!runLoading && !runId ? (
        <EmptyState
          title="No active M1 run found"
          description="Generate a plan from Dispatch to create M1 priority results, or let this page resolve the most recent run after one exists."
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
              detail="Resolved from query params, saved run context, or the latest M1 run."
              accent="ink"
            />
            <MetricCard
              label="Line Results"
              value={formatInteger(data.total_lines)}
              detail="Manifest lines scored by the M1 stub."
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
              detail={`${formatInteger(reeferLines)} reefer-sensitive lines are in this run.`}
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
            description="The planner-facing view of every manifest line scored by M1."
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
