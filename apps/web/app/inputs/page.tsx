"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getDcStock,
  getEtas,
  getLorryState,
  getManifests,
  getSalesHistory,
  getWarehouseStock,
  refreshAllInputs,
  refreshInputFamily,
} from "@/lib/api";
import {
  formatDate,
  formatDateTime,
  formatInteger,
  formatNumber,
  formatRelativeHours,
} from "@/lib/format";
import type {
  DcStockResponse,
  EtaResponse,
  InputRefreshFamily,
  InputRefreshResponse,
  LorryStateContract,
  ManifestResponse,
  SalesHistoryResponse,
  WarehouseStockContract,
} from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

const TABS = [
  { id: "manifests", label: "Manifests", actionFamily: "manifests" as const, actionLabel: "Reload Current State" },
  { id: "warehouse", label: "Warehouse Stock", actionFamily: "warehouse" as const, actionLabel: "Capture Snapshot" },
  { id: "dc", label: "DC Stock", actionFamily: "dc" as const, actionLabel: "Capture Snapshot" },
  { id: "sales", label: "Sales Forecasts", actionFamily: "sales" as const, actionLabel: "Reload Current State" },
  { id: "lorries", label: "Lorry State", actionFamily: "lorries" as const, actionLabel: "Capture Snapshot" },
  { id: "eta", label: "ETAs", actionFamily: "etas" as const, actionLabel: "Refresh ETAs" },
] as const;

type TabId = (typeof TABS)[number]["id"];
type NoticeState = { tone: "success" | "error"; title: string; message: string };

function formatFamilyTitle(family: InputRefreshFamily | "all") {
  if (family === "all") {
    return "Inputs";
  }

  const labels: Record<InputRefreshFamily, string> = {
    manifests: "Manifests",
    warehouse: "Warehouse",
    dc: "DC stock",
    sales: "Sales",
    lorries: "Lorries",
    etas: "ETAs",
  };

  return labels[family];
}

function buildRefreshNoticeMessage(family: InputRefreshFamily | "all", response: InputRefreshResponse) {
  if (family === "all") {
    return response.message;
  }

  const details = response.families[family];
  const relevantTime =
    details?.snapshot_time ??
    details?.latest_snapshot_time ??
    details?.latest_fetched_at ??
    details?.generated_at;

  if (!relevantTime) {
    return response.message;
  }

  return `${response.message} Latest timestamp: ${formatDateTime(relevantTime)}.`;
}

function parseApiError(error: unknown, fallbackTitle: string): NoticeState {
  if (error instanceof ApiError) {
    const detail = error.detail as
      | {
          detail?: { message?: string };
          message?: string;
        }
      | undefined;
    return {
      tone: "error",
      title: fallbackTitle,
      message: detail?.detail?.message ?? detail?.message ?? error.message,
    };
  }
  return {
    tone: "error",
    title: fallbackTitle,
    message: error instanceof Error ? error.message : "Unknown input refresh error.",
  };
}

export default function InputsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("manifests");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [manifests, setManifests] = useState<ManifestResponse | null>(null);
  const [warehouse, setWarehouse] = useState<WarehouseStockContract | null>(null);
  const [dcStock, setDcStock] = useState<DcStockResponse | null>(null);
  const [sales, setSales] = useState<SalesHistoryResponse | null>(null);
  const [lorries, setLorries] = useState<LorryStateContract | null>(null);
  const [etas, setEtas] = useState<EtaResponse | null>(null);

  async function loadCurrentInputs() {
    const [manifestData, warehouseData, dcData, salesData, lorryData, etaData] = await Promise.all([
      getManifests(),
      getWarehouseStock(),
      getDcStock(),
      getSalesHistory(),
      getLorryState(),
      getEtas(),
    ]);

    setManifests(manifestData);
    setWarehouse(warehouseData);
    setDcStock(dcData);
    setSales(salesData);
    setLorries(lorryData);
    setEtas(etaData);
  }

  async function refreshAndReload(
    family: InputRefreshFamily | "all",
    options: { showPageLoader?: boolean; notifySuccess?: boolean } = {}
  ) {
    const { showPageLoader = false, notifySuccess = true } = options;

    if (showPageLoader) {
      setLoading(true);
    } else {
      setActionLoading(true);
    }

    setError(null);
    if (notifySuccess) {
      setNotice(null);
    }

    try {
      const response = family === "all" ? await refreshAllInputs() : await refreshInputFamily(family);
      await loadCurrentInputs();

      if (notifySuccess) {
        setNotice({
          tone: "success",
          title: `${formatFamilyTitle(family)} refreshed`,
          message: buildRefreshNoticeMessage(family, response),
        });
      }
    } catch (cause) {
      if (showPageLoader) {
        setError(cause instanceof Error ? cause.message : "Unable to refresh planner inputs.");
      } else {
        setNotice(parseApiError(cause, "Inputs refresh failed"));
      }
    } finally {
      if (showPageLoader) {
        setLoading(false);
      } else {
        setActionLoading(false);
      }
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setLoading(true);
      setError(null);
      try {
        await refreshAllInputs();
        if (cancelled) {
          return;
        }
        await loadCurrentInputs();
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Unable to load planner inputs.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalManifestLines = useMemo(
    () => manifests?.manifests.reduce((sum, manifest) => sum + manifest.lines.length, 0) ?? 0,
    [manifests]
  );

  const activeTabConfig = TABS.find((tab) => tab.id === activeTab) ?? TABS[0];
  const latestDcSnapshotTime = useMemo(() => {
    const values = (dcStock?.dcs ?? []).map((dc) => dc.snapshot_time).filter(Boolean);
    return values.length ? [...values].sort().reverse()[0] : null;
  }, [dcStock]);
  const latestEtaFetchedAt = useMemo(() => {
    if (etas?.latest_fetched_at) {
      return etas.latest_fetched_at;
    }
    const values = (etas?.etas ?? []).map((eta) => eta.fetched_at).filter(Boolean);
    return values.length ? [...values].sort().reverse()[0] : null;
  }, [etas]);

  return (
    <div className="page-stack">
      <PageHeader
        title="Inputs"
        description="Read-only source data snapshots used to generate requests, priorities, and dispatch plans."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void refreshAndReload("all")}
              disabled={loading || actionLoading}
            >
              Refresh Inputs
            </button>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Refreshing input snapshots..." /> : null}
      {error ? (
        <div className="notice notice-error">
          <p>{error}</p>
        </div>
      ) : null}
      {notice ? (
        <div className={`notice notice-${notice.tone}`}>
          <h4>{notice.title}</h4>
          <p>{notice.message}</p>
        </div>
      ) : null}

      {manifests && warehouse && dcStock && sales && lorries && etas ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Manifest Lines"
              value={formatInteger(totalManifestLines)}
              detail={
                manifests.latest_snapshot_time
                  ? `Latest manifest snapshot ${formatDateTime(manifests.latest_snapshot_time)}.`
                  : "No active manifests in the current DB state."
              }
              accent="teal"
            />
            <MetricCard
              label="Warehouse SKUs"
              value={formatInteger(warehouse.items.length)}
              detail={`Snapshot captured ${formatDateTime(warehouse.snapshot_time)}.`}
              accent="ink"
            />
            <MetricCard
              label="DC Snapshots"
              value={formatInteger(dcStock.count)}
              detail={
                latestDcSnapshotTime
                  ? `Latest DC capture ${formatDateTime(latestDcSnapshotTime)}.`
                  : "No DC snapshots available."
              }
              accent="amber"
            />
            <MetricCard
              label="Fleet Records"
              value={formatInteger(lorries.lorries.length)}
              detail={
                latestEtaFetchedAt
                  ? `Lorry snapshot ${formatDateTime(lorries.snapshot_time)} | ETA refresh ${formatDateTime(latestEtaFetchedAt)}.`
                  : `Lorry snapshot ${formatDateTime(lorries.snapshot_time)}.`
              }
              accent="rose"
            />
          </div>

          <SectionCard
            title="Input Families"
            description="Opening this page auto-refreshes the mixed-mode planner inputs. Use the family tabs below for targeted follow-up actions."
          >
            <div className="tab-row">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={`tab-button${activeTab === tab.id ? " tab-button-active" : ""}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </SectionCard>

          {activeTab === "manifests" ? (
            <SectionCard
              title="Active Manifests"
              description={`Latest DB manifest state${manifests.latest_snapshot_time ? ` | ${formatDateTime(manifests.latest_snapshot_time)}` : ""}`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              {manifests.manifests.length ? (
                <div className="panel-grid">
                  {manifests.manifests.map((manifest) => (
                    <article key={manifest.manifest_snapshot_id} className="manifest-card">
                      <div className="manifest-card-header">
                        <div>
                          <h4>{manifest.manifest_name}</h4>
                          <p>
                            {manifest.vessel_name} <span className="subtle-text">({manifest.vessel_code})</span>
                          </p>
                          <p>Snapshot at {formatDateTime(manifest.snapshot_time)}</p>
                        </div>
                        <StatusPill value={manifest.status} />
                      </div>
                      <DataTable
                        columns={[
                          { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                          { key: "qty", header: "Quantity", render: (row) => formatInteger(row.quantity) },
                          {
                            key: "reefer",
                            header: "Cold Chain",
                            render: (row) => (row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal"),
                          },
                        ]}
                        rows={manifest.lines}
                        getRowKey={(row) => row.manifest_line_id}
                      />
                    </article>
                  ))}
                </div>
              ) : (
                <p className="subtle-text">No active manifests are available in the current database state.</p>
              )}
            </SectionCard>
          ) : null}

          {activeTab === "warehouse" ? (
            <SectionCard
              title="Warehouse Effective Stock"
              description={`Latest warehouse snapshot | ${formatDateTime(warehouse.snapshot_time)}`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              <DataTable
                columns={[
                  { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                  { key: "physical", header: "Physical", render: (row) => formatInteger(row.physical) },
                  { key: "reserved", header: "Reserved", render: (row) => formatInteger(row.reserved) },
                  { key: "effective", header: "Effective", render: (row) => formatInteger(row.effective) },
                  {
                    key: "reefer",
                    header: "Cold Chain",
                    render: (row) => (row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal"),
                  },
                ]}
                rows={warehouse.items}
                getRowKey={(row) => row.sku_id}
              />
            </SectionCard>
          ) : null}

          {activeTab === "dc" ? (
            <SectionCard
              title="DC Effective Stock"
              description={`Latest DC capture${latestDcSnapshotTime ? ` | ${formatDateTime(latestDcSnapshotTime)}` : ""}`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              <div className="panel-grid">
                {dcStock.dcs.map((dc) => (
                  <article key={dc.dc_id} className="manifest-card">
                    <div className="manifest-card-header">
                      <div>
                        <h4>
                          {dc.dc_name} <span className="subtle-text">({dc.dc_code})</span>
                        </h4>
                        <p>Snapshot at {formatDateTime(dc.snapshot_time)}</p>
                      </div>
                      <span className="detail-chip">{formatInteger(dc.items.length)} SKUs</span>
                    </div>
                    <DataTable
                      columns={[
                        { key: "sku", header: "SKU", render: (row) => row.sku_code },
                        { key: "physical", header: "Physical", render: (row) => formatInteger(row.physical) },
                        { key: "inTransit", header: "In Transit", render: (row) => formatInteger(row.in_transit) },
                        { key: "effective", header: "Effective", render: (row) => formatInteger(row.effective) },
                      ]}
                      rows={dc.items}
                      getRowKey={(row) => row.sku_id}
                    />
                  </article>
                ))}
              </div>
            </SectionCard>
          ) : null}

          {activeTab === "sales" ? (
            <SectionCard
              title="Sales History Forecasts"
              description={`Forecast generated ${formatDateTime(sales.generated_at)} from the trailing ${sales.lookback_days ?? 30} days of sales records.`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              <DataTable
                columns={[
                  { key: "dc", header: "DC", render: (row) => row.dc_code },
                  { key: "sku", header: "SKU", render: (row) => row.sku_code },
                  { key: "sold", header: "Sold 30d", render: (row) => formatInteger(row.total_sold_30d) },
                  { key: "daily", header: "Daily Avg", render: (row) => formatNumber(row.daily_avg) },
                  { key: "forecast", header: "Forecast 48h", render: (row) => formatNumber(row.forecast_48h) },
                ]}
                rows={sales.forecasts}
                getRowKey={(row, index) => `${row.dc_id}-${row.sku_id}-${index}`}
              />
            </SectionCard>
          ) : null}

          {activeTab === "lorries" ? (
            <SectionCard
              title="Lorry Availability"
              description={`Base snapshot ${formatDateTime(lorries.snapshot_time)} | Day 1 ${formatDate(lorries.planning_dates[0])} | Day 2 ${formatDate(lorries.planning_dates[1])}`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              <DataTable
                columns={[
                  { key: "reg", header: "Registration", render: (row) => row.registration },
                  { key: "type", header: "Type", render: (row) => <StatusPill value={row.lorry_type} tone="info" /> },
                  { key: "capacity", header: "Capacity", render: (row) => formatInteger(row.capacity_units) },
                  { key: "status", header: "Base", render: (row) => <StatusPill value={row.status} /> },
                  { key: "day1", header: "Day 1", render: (row) => <StatusPill value={row.day1_status} /> },
                  { key: "day2", header: "Day 2", render: (row) => <StatusPill value={row.day2_status} /> },
                ]}
                rows={lorries.lorries}
                getRowKey={(row) => row.lorry_id}
              />
            </SectionCard>
          ) : null}

          {activeTab === "eta" ? (
            <SectionCard
              title="Vessel ETAs"
              description={`Latest ETA refresh${latestEtaFetchedAt ? ` | ${formatDateTime(latestEtaFetchedAt)}` : ""}`}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => void refreshAndReload(activeTabConfig.actionFamily)}
                  disabled={actionLoading}
                >
                  {activeTabConfig.actionLabel}
                </button>
              }
            >
              <DataTable
                columns={[
                  { key: "vessel", header: "Vessel", render: (row) => `${row.vessel_name} (${row.vessel_code})` },
                  { key: "eta", header: "ETA", render: (row) => formatDateTime(row.eta_time) },
                  { key: "fetched", header: "Fetched At", render: (row) => formatDateTime(row.fetched_at) },
                  { key: "hours", header: "Hours Out", render: (row) => formatRelativeHours(row.hours_until_arrival) },
                  { key: "source", header: "Source", render: (row) => row.source },
                ]}
                rows={etas.etas}
                getRowKey={(row) => `${row.vessel_id}-${row.fetched_at}`}
              />
            </SectionCard>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
