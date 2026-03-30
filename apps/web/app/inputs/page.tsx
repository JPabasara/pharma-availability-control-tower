"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getDcStock,
  getEtas,
  getLorryState,
  getManifests,
  getSalesHistory,
  getWarehouseStock,
} from "@/lib/api";
import {
  formatDateTime,
  formatInteger,
  formatNumber,
  formatRelativeHours,
} from "@/lib/format";
import type {
  DcStockResponse,
  EtaResponse,
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
  { id: "manifests", label: "Manifests" },
  { id: "warehouse", label: "Warehouse Stock" },
  { id: "dc", label: "DC Stock" },
  { id: "sales", label: "Sales Forecasts" },
  { id: "lorries", label: "Lorry State" },
  { id: "eta", label: "ETAs" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function InputsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("manifests");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manifests, setManifests] = useState<ManifestResponse | null>(null);
  const [warehouse, setWarehouse] = useState<WarehouseStockContract | null>(null);
  const [dcStock, setDcStock] = useState<DcStockResponse | null>(null);
  const [sales, setSales] = useState<SalesHistoryResponse | null>(null);
  const [lorries, setLorries] = useState<LorryStateContract | null>(null);
  const [etas, setEtas] = useState<EtaResponse | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [manifestData, warehouseData, dcData, salesData, lorryData, etaData] =
          await Promise.all([
            getManifests(),
            getWarehouseStock(),
            getDcStock(),
            getSalesHistory(),
            getLorryState(),
            getEtas(),
          ]);

        if (!ignore) {
          setManifests(manifestData);
          setWarehouse(warehouseData);
          setDcStock(dcData);
          setSales(salesData);
          setLorries(lorryData);
          setEtas(etaData);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load planner inputs.");
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

  const totalManifestLines = useMemo(
    () => manifests?.manifests.reduce((sum, manifest) => sum + manifest.lines.length, 0) ?? 0,
    [manifests]
  );

  return (
    <div className="page-stack">
      <PageHeader
        title="Inputs"
        description="Read-only source data snapshots used to generate requests, priorities, and dispatch plans."
      />

      {loading ? <LoadingPanel label="Loading input snapshots..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {manifests && warehouse && dcStock && sales && lorries && etas ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Manifest Lines"
              value={formatInteger(totalManifestLines)}
              detail={`${formatInteger(manifests.count)} active vessel manifests feeding M1.`}
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
              detail="Five deterministic DC states seeded for the laptop demo."
              accent="amber"
            />
            <MetricCard
              label="Fleet Records"
              value={formatInteger(lorries.lorries.length)}
              detail={`ETA records available for ${formatInteger(etas.count)} vessels.`}
              accent="rose"
            />
          </div>

          <SectionCard
            title="Input Families"
            description="Switch between the planner inputs exactly as the backend exposes them."
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
              description="Manifest headers and shipment lines available to the priority engine."
            >
              <div className="panel-grid">
                {manifests.manifests.map((manifest) => (
                  <article key={manifest.manifest_snapshot_id} className="manifest-card">
                    <div className="manifest-card-header">
                      <div>
                        <h4>
                          {manifest.vessel_name} <span className="subtle-text">({manifest.vessel_code})</span>
                        </h4>
                        <p>Snapshot at {formatDateTime(manifest.snapshot_time)}</p>
                      </div>
                      <StatusPill value={manifest.status} />
                    </div>
                    <DataTable
                      columns={[
                        { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                        {
                          key: "qty",
                          header: "Quantity",
                          render: (row) => formatInteger(row.quantity),
                        },
                        {
                          key: "reefer",
                          header: "Cold Chain",
                          render: (row) =>
                            row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal",
                        },
                      ]}
                      rows={manifest.lines}
                      getRowKey={(row) => row.manifest_line_id}
                    />
                  </article>
                ))}
              </div>
            </SectionCard>
          ) : null}

          {activeTab === "warehouse" ? (
            <SectionCard
              title="Warehouse Effective Stock"
              description="Physical minus active reservations from the latest warehouse snapshot."
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
                    render: (row) =>
                      row.reefer_required ? <StatusPill value="reefer" tone="info" /> : "Normal",
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
              description="Physical plus in-transit quantities by DC."
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
              description="48-hour demand forecasts derived from the last seven days of seeded sales data."
            >
              <DataTable
                columns={[
                  { key: "dc", header: "DC", render: (row) => row.dc_code },
                  { key: "sku", header: "SKU", render: (row) => row.sku_code },
                  { key: "sold", header: "Sold 7d", render: (row) => formatInteger(row.total_sold_7d) },
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
              description="Binary availability snapshot used by M3 when generating candidate plans."
            >
              <DataTable
                columns={[
                  { key: "reg", header: "Registration", render: (row) => row.registration },
                  { key: "type", header: "Type", render: (row) => <StatusPill value={row.lorry_type} tone="info" /> },
                  { key: "capacity", header: "Capacity", render: (row) => formatInteger(row.capacity_units) },
                  { key: "status", header: "Status", render: (row) => <StatusPill value={row.status} /> },
                ]}
                rows={lorries.lorries}
                getRowKey={(row) => row.lorry_id}
              />
            </SectionCard>
          ) : null}

          {activeTab === "eta" ? (
            <SectionCard
              title="Vessel ETAs"
              description="Latest ETA snapshots from the mock provider."
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
                getRowKey={(row) => row.vessel_id}
              />
            </SectionCard>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
