"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";

import { getDashboardSummary } from "@/lib/api";
import { formatDate, formatDateTime, formatInteger } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

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
  }, [reloadKey]);

  const chartData = summary
    ? [
        { name: "Available", value: summary.fleet_status.available, color: "var(--color-teal)" },
        { name: "Assigned", value: summary.fleet_status.assigned, color: "var(--color-amber)" },
        { name: "Unavailable", value: summary.fleet_status.unavailable, color: "var(--color-border-hover)" },
      ]
    : [];

  return (
    <div className="page-stack">
      <PageHeader
        title="Dashboard"
        actions={
          <div className="page-actions">
            <Link href="/dispatch" className="button button-primary">
              Open Dispatch
            </Link>
            <Link href="/inputs" className="button button-secondary">
              Review Inputs
            </Link>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setReloadKey((current) => current + 1)}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
        }
      />

      {loading ? <LoadingPanel label="Loading dashboard summary..." /> : null}
      {error ? <div className="notice notice-error"><p>{error}</p></div> : null}

      {summary ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Prioritizer"
              value={
                summary.live_snapshots.m1.generated_at
                  ? formatDateTime(summary.live_snapshots.m1.generated_at)
                  : "Not yet"
              }
              detail="Latest priority refresh."
              accent="ink"
            />
            <MetricCard
              label="Forecaster"
              value={
                summary.live_snapshots.m2.generated_at
                  ? formatDateTime(summary.live_snapshots.m2.generated_at)
                  : "Not yet"
              }
              detail="Latest replenishment refresh."
              accent="amber"
            />
            <MetricCard
              label="Optimizer"
              value={
                summary.live_snapshots.m3.generated_at
                  ? formatDateTime(summary.live_snapshots.m3.generated_at)
                  : "Not yet"
              }
              detail="Latest live dispatch generation time."
              accent="teal"
            />
            <MetricCard
              label="Optimizer Status"
              value={summary.m3_lock.locked ? "Locked" : "Open"}
              detail={
                summary.m3_lock.locked
                  ? summary.m3_lock.lock_reason ?? "Current planning horizon is already approved."
                  : `Current Day 1 starts on ${formatDate(summary.m3_lock.planning_start_date)}.`
              }
              accent="rose"
            />
          </div>

          <div className="two-up-grid">
            <SectionCard
              title="Live Planning Workspace"
            >
              <div className="stack-list">
                <div className="list-card">
                  <h4>Prioritizer</h4>
                  <p>
                    {summary.live_snapshots.m1.available
                      ? `Updated ${formatDateTime(summary.live_snapshots.m1.generated_at)}.`
                      : "No live Prioritizer snapshot yet."}
                  </p>
                </div>
                <div className="list-card">
                  <h4>Forecaster</h4>
                  <p>
                    {summary.live_snapshots.m2.available
                      ? `Updated ${formatDateTime(summary.live_snapshots.m2.generated_at)}.`
                      : "No live Forecaster snapshot yet."}
                  </p>
                </div>
                <div className="list-card">
                  <h4>Optimizer</h4>
                  <p>
                    {summary.live_snapshots.m3.available
                      ? `Updated ${formatDateTime(summary.live_snapshots.m3.generated_at)}.`
                      : "No live Optimizer candidate set yet."}
                  </p>
                  <div className="detail-list">
                    <span className="detail-chip">Approved plans {formatInteger(summary.approved_plans)}</span>
                    <span className="detail-chip">Active manifests {formatInteger(summary.active_manifests)}</span>
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              title="Fleet Status"
              description={`Tomorrow's Schedule | ${formatDate(summary.fleet_status.business_date)}`}
            >
              <div className="split-layout" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "center" }}>
                <div style={{ width: "100%", height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--color-surface)",
                          borderColor: "var(--color-border)",
                          borderRadius: "8px",
                          color: "var(--color-ink)",
                        }}
                        itemStyle={{ color: "var(--color-ink)" }}
                      />
                      <Legend
                        verticalAlign="bottom"
                        height={36}
                        wrapperStyle={{ color: "var(--color-ink-soft)", fontSize: "0.85rem" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="cards-grid" style={{ gridTemplateColumns: "1fr" }}>
                  <div className="list-card">
                    <h4>{formatInteger(summary.fleet_status.available)} available</h4>
                    <p>Lorries currently free to be planned for tomorrow.</p>
                  </div>
                  <div className="list-card">
                    <h4>{formatInteger(summary.fleet_status.assigned)} assigned</h4>
                    <p>Lorries already committed to an approved Day 1 run.</p>
                  </div>
                  <div className="list-card">
                    <h4>{formatInteger(summary.fleet_status.unavailable)} unavailable</h4>
                    <p>Total fleet size is {formatInteger(summary.fleet_status.total)} vehicles in tomorrow&apos;s horizon.</p>
                  </div>
                </div>
              </div>
            </SectionCard>
          </div>

          <SectionCard
            title="Planner Alerts"
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
              <EmptyState
                title="No active alerts"
                description="The current stock and fleet checks are clear."
              />
            )}
          </SectionCard>
        </>
      ) : null}
    </div>
  );
}
