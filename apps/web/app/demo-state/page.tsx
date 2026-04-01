"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  arriveExecutionStop,
  arriveManifest,
  getArrivalEvents,
  getDcStock,
  getEtas,
  getLorryHorizon,
  getManifests,
  getOpenExecutionStops,
  getReservations,
  getStockSummary,
  getTransfers,
  postDcSale,
  setLorryAvailability,
  uploadManifest,
} from "@/lib/api";
import { formatDateTime, formatInteger } from "@/lib/format";
import type {
  ArrivalEvent,
  DcStockResponse,
  DemoReservation,
  DemoTransfer,
  EtaResponse,
  LorryStateContract,
  ManifestResponse,
  OpenExecutionStop,
  StockSummary,
} from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

const WORKSPACES = [
  { id: "state", label: "State View" },
  { id: "manifests", label: "Manifest Control" },
  { id: "dc", label: "DC Control" },
  { id: "lorries", label: "Lorry Control" },
  { id: "execution", label: "Execution" },
] as const;

type WorkspaceId = (typeof WORKSPACES)[number]["id"];
type NoticeState = { tone: "success" | "error" | "info"; title: string; message: string; items?: string[] };

function parseApiError(error: unknown): NoticeState {
  if (error instanceof ApiError) {
    const detail = error.detail as
      | {
          detail?: { message?: string; validation?: { errors?: string[] } };
          message?: string;
          validation?: { errors?: string[] };
        }
      | undefined;
    const nested = detail?.detail;
    const validation = nested?.validation ?? detail?.validation;
    return {
      tone: "error",
      title: "Operation failed",
      message: nested?.message ?? detail?.message ?? error.message,
      items: validation?.errors?.length ? validation.errors : undefined,
    };
  }
  return {
    tone: "error",
    title: "Operation failed",
    message: error instanceof Error ? error.message : "Unknown demo operation error.",
  };
}

export default function DemoStatePage() {
  const [workspace, setWorkspace] = useState<WorkspaceId>("state");
  const [stockSummary, setStockSummary] = useState<StockSummary | null>(null);
  const [reservations, setReservations] = useState<DemoReservation[]>([]);
  const [transfers, setTransfers] = useState<DemoTransfer[]>([]);
  const [events, setEvents] = useState<ArrivalEvent[]>([]);
  const [manifests, setManifests] = useState<ManifestResponse | null>(null);
  const [etas, setEtas] = useState<EtaResponse | null>(null);
  const [dcStock, setDcStock] = useState<DcStockResponse | null>(null);
  const [lorryHorizon, setLorryHorizon] = useState<LorryStateContract | null>(null);
  const [openStops, setOpenStops] = useState<OpenExecutionStop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [manifestName, setManifestName] = useState("");
  const [selectedVesselId, setSelectedVesselId] = useState<number | null>(null);
  const [manifestFile, setManifestFile] = useState<File | null>(null);
  const [manifestFileKey, setManifestFileKey] = useState(0);
  const [selectedDcId, setSelectedDcId] = useState<number | null>(null);
  const [selectedSkuId, setSelectedSkuId] = useState<number | null>(null);
  const [saleQuantity, setSaleQuantity] = useState("0");

  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [stock, reservationData, transferData, eventData, manifestData, etaData, dcData, lorryData, executionData] =
          await Promise.all([
            getStockSummary(),
            getReservations(),
            getTransfers(),
            getArrivalEvents(),
            getManifests(),
            getEtas(),
            getDcStock(),
            getLorryHorizon(),
            getOpenExecutionStops(),
          ]);
        if (!ignore) {
          setStockSummary(stock);
          setReservations(reservationData.reservations);
          setTransfers(transferData.transfers);
          setEvents(eventData.events);
          setManifests(manifestData);
          setEtas(etaData);
          setDcStock(dcData);
          setLorryHorizon(lorryData);
          setOpenStops(executionData.open_stops);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load demo operations.");
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
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedVesselId && etas?.etas[0]) {
      setSelectedVesselId(etas.etas[0].vessel_id);
    }
  }, [etas, selectedVesselId]);

  useEffect(() => {
    if (!selectedDcId && dcStock?.dcs[0]) {
      setSelectedDcId(dcStock.dcs[0].dc_id);
    }
  }, [dcStock, selectedDcId]);

  const selectedDc = useMemo(
    () => dcStock?.dcs.find((dc) => dc.dc_id === selectedDcId) ?? null,
    [dcStock, selectedDcId]
  );

  useEffect(() => {
    if (!selectedDc?.items.length) {
      return;
    }
    if (!selectedSkuId || !selectedDc.items.some((item) => item.sku_id === selectedSkuId)) {
      setSelectedSkuId(selectedDc.items[0].sku_id);
    }
  }, [selectedDc, selectedSkuId]);

  async function handleManifestUpload() {
    if (!manifestName.trim() || !selectedVesselId || !manifestFile) {
      setNotice({
        tone: "error",
        title: "Manifest upload is incomplete",
        message: "Add a manifest name, choose a vessel, and attach a CSV before uploading.",
      });
      return;
    }
    setActionLoading(true);
    setNotice(null);
    try {
      const formData = new FormData();
      formData.set("manifest_name", manifestName.trim());
      formData.set("vessel_id", String(selectedVesselId));
      formData.set("file", manifestFile);
      const response = await uploadManifest(formData);
      setNotice({ tone: "success", title: "Manifest uploaded", message: response.message });
      setManifestName("");
      setManifestFile(null);
      setManifestFileKey((current) => current + 1);
      setReloadKey((current) => current + 1);
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleManifestArrival(manifestId: number) {
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await arriveManifest(manifestId);
      setNotice({ tone: "success", title: "Manifest arrived", message: response.message });
      setReloadKey((current) => current + 1);
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDcSale() {
    const quantity = Number(saleQuantity);
    if (!selectedDcId || !selectedSkuId || quantity <= 0) {
      setNotice({
        tone: "error",
        title: "DC sale is incomplete",
        message: "Choose a DC, choose a SKU, and enter a positive quantity.",
      });
      return;
    }
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await postDcSale(selectedDcId, selectedSkuId, quantity);
      setNotice({ tone: "success", title: "DC sale posted", message: response.message });
      setSaleQuantity("0");
      setReloadKey((current) => current + 1);
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleLorryToggle(lorryId: number, targetStatus: "available" | "unavailable") {
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await setLorryAvailability(lorryId, targetStatus);
      setNotice({ tone: "success", title: "Lorry horizon updated", message: response.message });
      setReloadKey((current) => current + 1);
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStopArrival(planStopId: number) {
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await arriveExecutionStop(planStopId);
      setNotice({ tone: "success", title: "Stop arrived", message: response.message });
      setReloadKey((current) => current + 1);
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Demo Operations"
        description="Hosted business actions for manifests, DC sales, lorry horizon control, and stop arrivals, with the current demo state always visible."
        actions={
          <div className="page-actions">
            <button type="button" className="button button-secondary" onClick={() => setReloadKey((current) => current + 1)} disabled={loading || actionLoading}>
              Refresh
            </button>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading demo operations..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}
      {notice ? (
        <div className={`notice notice-${notice.tone}`}>
          <h4>{notice.title}</h4>
          <p>{notice.message}</p>
          {notice.items?.length ? <ul>{notice.items.map((item) => <li key={item}>{item}</li>)}</ul> : null}
        </div>
      ) : null}

      {stockSummary ? (
        <div className="metric-grid">
          <MetricCard label="WH Physical" value={formatInteger(stockSummary.totals.total_wh_physical)} detail="Current physical warehouse stock." accent="ink" />
          <MetricCard label="WH Reserved" value={formatInteger(stockSummary.totals.total_wh_reserved)} detail="Active warehouse reservations from approved plans." accent="rose" />
          <MetricCard label="DC In Transit" value={formatInteger(stockSummary.totals.total_dc_in_transit)} detail="Transfer quantity still moving toward the DC network." accent="amber" />
          <MetricCard label="DC Effective" value={formatInteger(stockSummary.totals.total_dc_effective)} detail="Current effective DC inventory across all locations." accent="teal" />
        </div>
      ) : null}

      <SectionCard
        title="Workspace"
        description="Keep the route stable at /demo-state while switching between the current state view and hosted operational controls."
      >
        <div className="field-grid">
          <div className="form-field">
            <label htmlFor="workspace">Workspace</label>
            <select id="workspace" value={workspace} onChange={(event) => setWorkspace(event.target.value as WorkspaceId)}>
              {WORKSPACES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </div>
          {lorryHorizon ? (
            <div className="operation-panel">
              <h4>2-Day Horizon</h4>
              <p className="subtle-text">
                {lorryHorizon.planning_dates.map((value, index) => `Day ${index + 1}: ${value}`).join(" | ")}
              </p>
            </div>
          ) : null}
        </div>
      </SectionCard>

      {workspace === "state" ? (
        <>
          {!loading && !reservations.length && !transfers.length ? (
            <EmptyState
              title="No demo-state mutations yet"
              description="Approve a plan from Dispatch to create reservations and transfers, then use the hosted manifest, lorry, and execution controls here to advance the business state."
              actionHref="/dispatch"
              actionLabel="Open Dispatch"
            />
          ) : null}

          <SectionCard title="Reservations" description="Warehouse-side reservations created when a plan version is approved.">
            <DataTable
              columns={[
                { key: "plan", header: "Plan", render: (row) => `#${row.plan_version_id}` },
                { key: "stop", header: "Stop", render: (row) => row.plan_stop_id ? `#${row.plan_stop_id}` : "Legacy" },
                { key: "sku", header: "SKU", render: (row) => `${row.sku_code} - ${row.sku_name}` },
                { key: "qty", header: "Reserved", render: (row) => formatInteger(row.quantity_reserved) },
                { key: "status", header: "Status", render: (row) => <StatusPill value={row.status} /> },
                { key: "created", header: "Created", render: (row) => formatDateTime(row.created_at) },
              ]}
              rows={reservations}
              getRowKey={(row) => row.id}
              emptyText="No reservations have been created yet."
            />
          </SectionCard>

          <SectionCard title="Transfers" description="DC-side transfer records created from approved plan items.">
            <DataTable
              columns={[
                { key: "plan", header: "Plan", render: (row) => `#${row.plan_version_id}` },
                { key: "day", header: "Day", render: (row) => row.dispatch_day ? `Day ${row.dispatch_day}` : "Unknown" },
                { key: "stop", header: "Stop", render: (row) => row.stop_sequence ? `#${row.stop_sequence}` : "Unknown" },
                { key: "lorry", header: "Lorry", render: (row) => `${row.registration} (${row.lorry_type})` },
                { key: "dc", header: "Destination", render: (row) => `${row.dc_code} - ${row.dc_name}` },
                { key: "sku", header: "SKU", render: (row) => row.sku_code },
                { key: "qty", header: "Quantity", render: (row) => formatInteger(row.quantity) },
                { key: "status", header: "Status", render: (row) => <StatusPill value={row.status} /> },
              ]}
              rows={transfers}
              getRowKey={(row) => row.id}
              emptyText="No transfers have been created yet."
            />
          </SectionCard>

          <SectionCard title="Business Events" description="Most recent manifest, DC sale, and lorry arrival events recorded by the hosted backend.">
            <DataTable
              columns={[
                { key: "type", header: "Event Type", render: (row) => <StatusPill value={row.event_type} tone="info" /> },
                { key: "ref", header: "Reference", render: (row) => `#${row.reference_id}` },
                { key: "time", header: "Event Time", render: (row) => formatDateTime(row.event_time) },
                { key: "details", header: "Details", render: (row) => JSON.stringify(row.details ?? {}), className: "mono" },
              ]}
              rows={events}
              getRowKey={(row) => row.id}
              emptyText="No business events have been recorded yet."
            />
          </SectionCard>
        </>
      ) : null}

      {workspace === "manifests" ? (
        <SectionCard title="Manifest Control" description="Upload new active manifests and mark them arrived to increase warehouse physical stock.">
          <div className="two-up-grid">
            <div className="operation-panel">
              <div className="field-grid">
                <div className="form-field">
                  <label htmlFor="manifest-name">Manifest Name</label>
                  <input id="manifest-name" value={manifestName} onChange={(event) => setManifestName(event.target.value)} placeholder="Inbound Manifest Gamma" />
                </div>
                <div className="form-field">
                  <label htmlFor="manifest-vessel">Vessel</label>
                  <select id="manifest-vessel" value={selectedVesselId ?? ""} onChange={(event) => setSelectedVesselId(Number(event.target.value))}>
                    {(etas?.etas ?? []).map((eta) => (
                      <option key={eta.vessel_id} value={eta.vessel_id}>
                        {eta.vessel_name} ({eta.vessel_code}) | ETA {formatDateTime(eta.eta_time)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="manifest-file">CSV File</label>
                  <input key={manifestFileKey} id="manifest-file" type="file" accept=".csv,text/csv" onChange={(event) => setManifestFile(event.target.files?.[0] ?? null)} />
                </div>
              </div>
              <p className="subtle-text">CSV columns: <span className="mono">sku_code,quantity</span>. Reefer rules still come from the SKU master.</p>
              <div className="toolbar">
                <button type="button" className="button button-primary" onClick={() => void handleManifestUpload()} disabled={actionLoading}>
                  Upload Manifest
                </button>
              </div>
            </div>

            <div className="operation-panel">
              <h4>Active Manifests</h4>
              {manifests?.manifests.length ? (
                <div className="stack-list">
                  {manifests.manifests.map((manifest) => (
                    <article key={manifest.manifest_snapshot_id} className="manifest-card">
                      <div className="manifest-card-header">
                        <div>
                          <h4>{manifest.manifest_name}</h4>
                          <p>{manifest.vessel_name} ({manifest.vessel_code})</p>
                          <p>Snapshot at {formatDateTime(manifest.snapshot_time)}</p>
                        </div>
                        <StatusPill value={manifest.status} />
                      </div>
                      <div className="detail-list">
                        <span className="detail-chip">{formatInteger(manifest.lines.length)} lines</span>
                        <span className="detail-chip">
                          {formatInteger(manifest.lines.reduce((sum, line) => sum + line.quantity, 0))} units
                        </span>
                      </div>
                      <div className="toolbar">
                        <button type="button" className="button button-secondary" onClick={() => void handleManifestArrival(manifest.manifest_snapshot_id)} disabled={actionLoading}>
                          Mark Arrived
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : <p className="subtle-text">No active manifests are waiting for arrival.</p>}
            </div>
          </div>
        </SectionCard>
      ) : null}

      {workspace === "dc" ? (
        <SectionCard title="DC Control" description="Post current-time DC sales to reduce physical stock and extend the 30-day sales history used by M2.">
          <div className="two-up-grid">
            <div className="operation-panel">
              <div className="field-grid">
                <div className="form-field">
                  <label htmlFor="dc-select">Distribution Center</label>
                  <select id="dc-select" value={selectedDcId ?? ""} onChange={(event) => setSelectedDcId(Number(event.target.value))}>
                    {(dcStock?.dcs ?? []).map((dc) => (
                      <option key={dc.dc_id} value={dc.dc_id}>
                        {dc.dc_code} - {dc.dc_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="dc-sku">SKU</label>
                  <select id="dc-sku" value={selectedSkuId ?? ""} onChange={(event) => setSelectedSkuId(Number(event.target.value))}>
                    {(selectedDc?.items ?? []).map((item) => (
                      <option key={item.sku_id} value={item.sku_id}>
                        {item.sku_code} - {item.sku_name} | physical {item.physical}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="dc-qty">Quantity Sold</label>
                  <input id="dc-qty" type="number" min={1} value={saleQuantity} onChange={(event) => setSaleQuantity(event.target.value)} />
                </div>
              </div>
              <div className="toolbar">
                <button type="button" className="button button-primary" onClick={() => void handleDcSale()} disabled={actionLoading}>
                  Post Sale
                </button>
              </div>
            </div>

            <div className="operation-panel">
              <h4>Selected DC Snapshot</h4>
              {selectedDc ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => row.sku_code },
                    { key: "physical", header: "Physical", render: (row) => formatInteger(row.physical) },
                    { key: "inTransit", header: "In Transit", render: (row) => formatInteger(row.in_transit) },
                    { key: "effective", header: "Effective", render: (row) => formatInteger(row.effective) },
                  ]}
                  rows={selectedDc.items}
                  getRowKey={(row) => row.sku_id}
                  emptyText="No SKU rows are available for this DC."
                />
              ) : <p className="subtle-text">Choose a DC to inspect its live stock picture.</p>}
            </div>
          </div>
        </SectionCard>
      ) : null}

      {workspace === "lorries" ? (
        <SectionCard title="Lorry Control" description="Toggle manual availability for the next two planning days unless the lorry is already assigned by an approved plan.">
          {lorryHorizon ? (
            <DataTable
              columns={[
                { key: "reg", header: "Registration", render: (row) => row.registration },
                { key: "type", header: "Type", render: (row) => <StatusPill value={row.lorry_type} tone="info" /> },
                { key: "day1", header: "Day 1", render: (row) => <StatusPill value={row.day1_status} /> },
                { key: "day2", header: "Day 2", render: (row) => <StatusPill value={row.day2_status} /> },
                {
                  key: "action",
                  header: "Action",
                  render: (row) => {
                    const isAssigned = row.day1_status === "assigned" || row.day2_status === "assigned";
                    const targetStatus =
                      row.day1_status === "unavailable" && row.day2_status === "unavailable"
                        ? "available"
                        : "unavailable";
                    return (
                      <button
                        type="button"
                        className="button button-secondary"
                        disabled={isAssigned || actionLoading}
                        onClick={() => void handleLorryToggle(row.lorry_id, targetStatus)}
                      >
                        {isAssigned ? "Assigned" : targetStatus === "available" ? "Set Available" : "Set Unavailable"}
                      </button>
                    );
                  },
                },
              ]}
              rows={lorryHorizon.lorries}
              getRowKey={(row) => row.lorry_id}
              emptyText="No lorry horizon data is available yet."
            />
          ) : <p className="subtle-text">No lorry horizon snapshot is available.</p>}
        </SectionCard>
      ) : null}

      {workspace === "execution" ? (
        <SectionCard title="Execution" description="Mark approved stop arrivals so warehouse reservations release and DC physical stock increases for that stop only.">
          {openStops.length ? (
            <div className="panel-grid">
              {openStops.map((stop) => (
                <article key={stop.plan_stop_id} className="manifest-card">
                  <div className="manifest-card-header">
                    <div>
                      <h4>Day {stop.dispatch_day} | Stop {stop.stop_sequence}</h4>
                      <p>{stop.registration} to {stop.dc_name} ({stop.dc_code})</p>
                      <p>Plan #{stop.plan_version_id} | Run #{stop.plan_run_id}</p>
                    </div>
                    <StatusPill value="in_transit" />
                  </div>
                  <div className="detail-list">
                    {stop.items.map((item) => (
                      <span key={item.transfer_id} className="detail-chip">
                        {item.sku_code}: {formatInteger(item.quantity)}
                      </span>
                    ))}
                  </div>
                  <div className="toolbar">
                    <button type="button" className="button button-primary" onClick={() => void handleStopArrival(stop.plan_stop_id)} disabled={actionLoading}>
                      Mark DC Arrived
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No open execution stops"
              description="Approve a plan first. Once transfers are in transit, their open stop arrivals will appear here."
              actionHref="/dispatch"
              actionLabel="Open Dispatch"
            />
          )}
        </SectionCard>
      ) : null}
    </div>
  );
}
