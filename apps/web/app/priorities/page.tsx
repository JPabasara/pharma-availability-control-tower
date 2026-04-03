"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, getCurrentM1Results, refreshM1 } from "@/lib/api";
import { formatDate, formatDateTime, formatInteger, formatNumber } from "@/lib/format";
import type { M1ResultsResponse, M1ShipmentSummary } from "@/lib/types";
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
  const [expandedShipments, setExpandedShipments] = useState<Set<number>>(new Set());

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

  function toggleShipment(snapId: number) {
    setExpandedShipments((prev) => {
      const next = new Set(prev);
      if (next.has(snapId)) {
        next.delete(snapId);
      } else {
        next.add(snapId);
      }
      return next;
    });
  }

  function expandAll() {
    if (data?.shipments) {
      setExpandedShipments(new Set(data.shipments.map((s) => s.manifest_snapshot_id)));
    }
  }

  function collapseAll() {
    setExpandedShipments(new Set());
  }

  const criticalShipments = useMemo(
    () => data?.shipments.filter((s) => s.shipment_band === "critical").length ?? 0,
    [data]
  );
  const coldChainShipments = useMemo(
    () => data?.shipments.filter((s) => s.has_cold_chain).length ?? 0,
    [data]
  );
  const topScore = useMemo(() => data?.shipments[0]?.shipment_score ?? 0, [data]);

  return (
    <div className="page-stack">
      <PageHeader
        title="Prioritizer"
        description="Shipment-level priority ranking for clearance team review. Expand each shipment to see per-SKU breakdown."
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
          description="Use Refresh M1 to regenerate M2 and M1, then review the latest priority results here."
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
                  : "Current Prioritizer snapshot."
              }
              accent="ink"
            />
            <MetricCard
              label="Total Shipments"
              value={formatInteger(data.total_shipments)}
              detail={`${formatInteger(data.total_lines)} manifest lines across all shipments.`}
              accent="teal"
            />
            <MetricCard
              label="Critical Shipments"
              value={formatInteger(criticalShipments)}
              detail="Shipments with critical priority requiring immediate clearance."
              accent="rose"
            />
            <MetricCard
              label="Top Score"
              value={formatNumber(topScore)}
              detail={`${formatInteger(coldChainShipments)} shipment(s) contain cold chain items.`}
              accent="amber"
            />
          </div>

          <SectionCard
            title="Shipment Priority Ranking"
            description="Ranked list of incoming shipments — clear the top-ranked shipment first."
          >
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <button type="button" className="button button-secondary" style={{ fontSize: "0.8rem", padding: "0.3rem 0.7rem" }} onClick={expandAll}>
                Expand All
              </button>
              <button type="button" className="button button-secondary" style={{ fontSize: "0.8rem", padding: "0.3rem 0.7rem" }} onClick={collapseAll}>
                Collapse All
              </button>
            </div>

            <div className="shipment-ranking-list">
              {data.shipments.map((shipment) => (
                <ShipmentRow
                  key={shipment.manifest_snapshot_id}
                  shipment={shipment}
                  expanded={expandedShipments.has(shipment.manifest_snapshot_id)}
                  onToggle={() => toggleShipment(shipment.manifest_snapshot_id)}
                />
              ))}
            </div>
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}

function ShipmentRow({
  shipment,
  expanded,
  onToggle,
}: {
  shipment: M1ShipmentSummary;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="shipment-card">
      <button
        type="button"
        className="shipment-header"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <div className="shipment-rank">#{shipment.rank}</div>
        <div className="shipment-meta">
          <span className="shipment-name">{shipment.manifest_name}</span>
          <span className="shipment-vessel">{shipment.vessel_name} ({shipment.vessel_code})</span>
        </div>
        <div className="shipment-stats">
          <StatusPill value={shipment.shipment_band} />
          <span className="shipment-score">{formatNumber(shipment.shipment_score)}</span>
          <span className="shipment-skus">{shipment.sku_count} SKUs</span>
          <span className="shipment-qty">{formatInteger(shipment.total_quantity)} units</span>
          {shipment.has_cold_chain ? (
            <StatusPill value="cold chain" tone="info" />
          ) : null}
        </div>
        <span className="shipment-chevron">{expanded ? "▼" : "▶"}</span>
      </button>

      {expanded ? (
        <div className="shipment-detail">
          <DataTable
            columns={[
              { key: "sku", header: "SKU", render: (row) => `${row.sku_code} — ${row.sku_name}` },
              { key: "quantity", header: "Quantity", render: (row) => formatInteger(row.quantity) },
              { key: "score", header: "Score", render: (row) => formatNumber(row.priority_score) },
              { key: "band", header: "Band", render: (row) => <StatusPill value={row.priority_band} /> },
              {
                key: "reefer",
                header: "Cold Chain",
                render: (row) =>
                  row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal",
              },
            ]}
            rows={shipment.lines}
            getRowKey={(row) => row.id}
          />
        </div>
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
