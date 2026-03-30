"use client";

import { useEffect, useState } from "react";

import {
  getArrivalEvents,
  getReservations,
  getStockSummary,
  getTransfers,
} from "@/lib/api";
import { formatDateTime, formatInteger } from "@/lib/format";
import type {
  ArrivalEvent,
  DemoReservation,
  DemoTransfer,
  StockSummary,
} from "@/lib/types";
import { DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

export default function DemoStatePage() {
  const [stockSummary, setStockSummary] = useState<StockSummary | null>(null);
  const [reservations, setReservations] = useState<DemoReservation[]>([]);
  const [transfers, setTransfers] = useState<DemoTransfer[]>([]);
  const [events, setEvents] = useState<ArrivalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [stock, reservationData, transferData, eventData] = await Promise.all([
          getStockSummary(),
          getReservations(),
          getTransfers(),
          getArrivalEvents(),
        ]);

        if (!ignore) {
          setStockSummary(stock);
          setReservations(reservationData.reservations);
          setTransfers(transferData.transfers);
          setEvents(eventData.events);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load demo-state.");
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

  return (
    <div className="page-stack">
      <PageHeader
        title="Demo State"
        description="Reservations, transfers, stock projections, and arrival events after planner decisions."
      />

      <div className="notice notice-info">
        <h4>CLI-driven arrivals</h4>
        <p>
          Vessel and lorry arrivals are still simulated by the backend scripts. This page is read-only and shows the resulting state.
        </p>
      </div>

      {loading ? <LoadingPanel label="Loading demo-state..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {stockSummary ? (
        <div className="metric-grid">
          <MetricCard
            label="WH Physical"
            value={formatInteger(stockSummary.totals.total_wh_physical)}
            detail="Current physical stock recorded at the warehouse."
            accent="ink"
          />
          <MetricCard
            label="WH Reserved"
            value={formatInteger(stockSummary.totals.total_wh_reserved)}
            detail="Active reservations created by approved plans."
            accent="rose"
          />
          <MetricCard
            label="DC In Transit"
            value={formatInteger(stockSummary.totals.total_dc_in_transit)}
            detail="Transfer quantity still moving toward the DC network."
            accent="amber"
          />
          <MetricCard
            label="DC Effective"
            value={formatInteger(stockSummary.totals.total_dc_effective)}
            detail="Current effective DC inventory across all seeded locations."
            accent="teal"
          />
        </div>
      ) : null}

      {!loading && !reservations.length && !transfers.length ? (
        <EmptyState
          title="No demo-state mutations yet"
          description="Approve a plan from Dispatch to create reservations and transfers, then use the CLI scripts to advance arrivals."
          actionHref="/dispatch"
          actionLabel="Open Dispatch"
        />
      ) : null}

      <SectionCard
        title="Reservations"
        description="Warehouse-side reservations created when a plan version is approved."
      >
        <DataTable
          columns={[
            { key: "plan", header: "Plan", render: (row) => `#${row.plan_version_id}` },
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

      <SectionCard
        title="Transfers"
        description="DC-side transfer records created from approved plan items."
      >
        <DataTable
          columns={[
            { key: "plan", header: "Plan", render: (row) => `#${row.plan_version_id}` },
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

      <SectionCard
        title="Arrival Events"
        description="Most recent simulated vessel and lorry arrival events."
      >
        <DataTable
          columns={[
            { key: "type", header: "Event Type", render: (row) => <StatusPill value={row.event_type} tone="info" /> },
            { key: "ref", header: "Reference", render: (row) => `#${row.reference_id}` },
            { key: "time", header: "Event Time", render: (row) => formatDateTime(row.event_time) },
            {
              key: "details",
              header: "Details",
              render: (row) => JSON.stringify(row.details ?? {}),
              className: "mono",
            },
          ]}
          rows={events}
          getRowKey={(row) => row.id}
          emptyText="No arrival events have been recorded yet."
        />
      </SectionCard>
    </div>
  );
}
