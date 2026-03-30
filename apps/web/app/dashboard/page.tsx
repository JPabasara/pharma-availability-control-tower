"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getDashboardSummary } from "@/lib/api";
import { formatDateTime, formatInteger } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getDashboardSummary();
        if (!ignore) {
          setSummary(response);
        }
      } catch (cause) {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : "Unable to load dashboard.");
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
        title="Dashboard"
        description="Live planner overview for shortages, fleet readiness, and the latest orchestration activity."
        actions={
          <div className="page-actions">
            <Link href="/dispatch" className="button button-primary">
              Open Dispatch
            </Link>
            <Link href="/inputs" className="button button-secondary">
              Review Inputs
            </Link>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading dashboard summary..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {summary ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Active Alerts"
              value={formatInteger(summary.alert_count)}
              detail="Dashboard warnings from effective stock and fleet pressure checks."
              accent="rose"
            />
            <MetricCard
              label="Pending Drafts"
              value={formatInteger(summary.pending_approvals)}
              detail="Draft plan versions waiting for planner action."
              accent="amber"
            />
            <MetricCard
              label="Approved Plans"
              value={formatInteger(summary.approved_plans)}
              detail="Frozen plan versions already committed to demo-state."
              accent="teal"
            />
            <MetricCard
              label="Active Manifests"
              value={formatInteger(summary.active_manifests)}
              detail="Inbound manifests still influencing planner priorities."
              accent="primary"
            />
          </div>

          <div className="two-up-grid">
            <SectionCard
              title="Latest Engine Activity"
              description="The planner console is on-demand, so runs only appear after a Generate Plan action."
            >
              {summary.latest_engine_run ? (
                <div className="stack-list">
                  <div className="list-card">
                    <h4>Run #{summary.latest_engine_run.id}</h4>
                    <p>
                      {summary.latest_engine_run.engine_type.toUpperCase()} finished with status{" "}
                      <StatusPill value={summary.latest_engine_run.status} />
                    </p>
                    <div className="detail-list">
                      <span className="detail-chip">
                        Started <strong>{formatDateTime(summary.latest_engine_run.started_at)}</strong>
                      </span>
                      <span className="detail-chip">
                        Completed <strong>{formatDateTime(summary.latest_engine_run.completed_at)}</strong>
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No engine runs yet"
                  description="The seeded database is ready, but no plan has been generated from the planner console yet."
                  actionHref="/dispatch"
                  actionLabel="Generate From Dispatch"
                />
              )}
            </SectionCard>

            <SectionCard
              title="Fleet Status"
              description="Availability from the latest lorry-state snapshot."
            >
              <div className="split-layout" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "center" }}>
                <div style={{ width: "100%", height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Normal Available', value: summary.fleet_status.normal_available, color: 'var(--color-teal)' },
                          { name: 'Reefer Available', value: summary.fleet_status.reefer_available, color: 'var(--color-primary)' },
                          { name: 'Unavailable', value: summary.fleet_status.unavailable, color: 'var(--color-ink-muted)' },
                        ]}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {[
                          { name: 'Normal Available', value: summary.fleet_status.normal_available, color: 'var(--color-teal)' },
                          { name: 'Reefer Available', value: summary.fleet_status.reefer_available, color: 'var(--color-primary)' },
                          { name: 'Unavailable', value: summary.fleet_status.unavailable, color: 'var(--color-border-hover)' },
                        ].map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'var(--color-surface)', 
                          borderColor: 'var(--color-border)',
                          borderRadius: '8px',
                          color: 'var(--color-ink)'
                        }} 
                        itemStyle={{ color: 'var(--color-ink)' }} 
                      />
                      <Legend verticalAlign="bottom" height={36} wrapperStyle={{ color: 'var(--color-ink-soft)', fontSize: '0.85rem' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="cards-grid" style={{ gridTemplateColumns: "1fr" }}>
                  <div className="list-card">
                    <h4>{formatInteger(summary.fleet_status.available)} available</h4>
                    <p>
                      {formatInteger(summary.fleet_status.normal_available)} normal and{" "}
                      {formatInteger(summary.fleet_status.reefer_available)} reefer lorries are currently ready.
                    </p>
                  </div>
                  <div className="list-card">
                    <h4>{formatInteger(summary.fleet_status.unavailable)} unavailable</h4>
                    <p>
                      Total fleet size is {formatInteger(summary.fleet_status.total)} vehicles across the 48-hour planning horizon.
                    </p>
                  </div>
                </div>
              </div>
            </SectionCard>
          </div>

          <SectionCard
            title="Planner Alerts"
            description="Critical DC shortages, warehouse pressure, and reefer constraints surfaced by the backend."
          >
            {summary.alerts.length ? (
              <div className="alert-list">
                {summary.alerts.map((alert, index) => (
                  <article
                    key={`${alert.type}-${alert.dc_id ?? index}`}
                    className={`alert-card alert-card-${alert.severity === "critical" ? "critical" : "warning"}`}
                  >
                    <div className="manifest-card-header">
                      <div>
                        <h4>{alert.message}</h4>
                        <p>{alert.type.replaceAll("_", " ")}</p>
                      </div>
                      <StatusPill value={alert.severity} />
                    </div>
                    {alert.details?.length ? (
                      <div className="detail-list">
                        {alert.details.map((item, detailIndex) => (
                          <span key={`${alert.type}-${detailIndex}`} className="detail-chip">
                            {Object.entries(item)
                              .map(([key, value]) => `${key}: ${value}`)
                              .join(" | ")}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle-text">No active alerts at the moment.</p>
            )}
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}
