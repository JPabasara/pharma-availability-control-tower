"use client";

import { Suspense, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  approvePlan,
  generatePlan,
  getCurrentM1Results,
  getCurrentM2Requests,
  getCurrentM3PlanDetail,
  getCurrentM3Plans,
  getDcStock,
  getLorryState,
  getWarehouseStock,
  overridePlan,
  rejectPlan,
} from "@/lib/api";
import { formatDate, formatDateTime, formatInteger, formatNumber, getPlanLabel } from "@/lib/format";
import type {
  DcStockContract,
  LorryState,
  M3PlanDetail,
  M3PlanSummary,
  OverrideRunPayload,
  WarehouseStockItem,
} from "@/lib/types";
import { DispatchOverrideEditor, type EditableRun, type EditableStop } from "@/components/DispatchOverrideEditor";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

type NoticeState = { tone: "success" | "error" | "info"; title: string; message: string; items?: string[] };

function makeId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function mapDetailToDraft(detail: M3PlanDetail): EditableRun[] {
  return detail.runs.map((run) => ({
    clientId: makeId("run"),
    lorry_id: run.lorry_id,
    dispatch_day: run.dispatch_day,
    stops: run.stops.map((stop) => ({
      clientId: makeId("stop"),
      dc_id: stop.dc_id,
      stop_sequence: stop.stop_sequence,
      items: stop.items.map((item) => ({
        clientId: makeId("item"),
        sku_id: item.sku_id,
        quantity: item.quantity,
      })),
    })),
  }));
}

function buildOverridePayload(runs: EditableRun[]): OverrideRunPayload[] {
  return runs.map((run) => ({
    lorry_id: run.lorry_id,
    dispatch_day: run.dispatch_day,
    stops: run.stops.map((stop) => ({
      dc_id: stop.dc_id,
      stop_sequence: stop.stop_sequence,
      items: stop.items
        .filter((item) => item.sku_id > 0 && item.quantity > 0)
        .map((item) => ({ sku_id: item.sku_id, quantity: item.quantity })),
    })),
  }));
}

function parseApiError(error: unknown): NoticeState {
  if (error instanceof ApiError) {
    const detail = error.detail as
      | {
          detail?: { message?: string; validation?: { errors?: string[]; warnings?: string[] } };
          message?: string;
          validation?: { errors?: string[]; warnings?: string[] };
        }
      | undefined;
    const nested = detail?.detail;
    const validation = nested?.validation ?? detail?.validation;
    return {
      tone: "error",
      title: "Planner action failed",
      message: nested?.message ?? detail?.message ?? error.message,
      items: validation?.errors?.length ? validation.errors : undefined,
    };
  }
  return {
    tone: "error",
    title: "Planner action failed",
    message: error instanceof Error ? error.message : "Unknown planner error.",
  };
}

function totalRunUnits(run: { stops: Array<{ items: Array<{ quantity: number }> }> }) {
  return run.stops.reduce(
    (sum, stop) => sum + stop.items.reduce((itemSum, item) => itemSum + item.quantity, 0),
    0
  );
}

function DispatchPageContent() {
  const [plans, setPlans] = useState<M3PlanSummary[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [detail, setDetail] = useState<M3PlanDetail | null>(null);
  const [draftRuns, setDraftRuns] = useState<EditableRun[]>([]);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [referenceLoading, setReferenceLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [lorryOptions, setLorryOptions] = useState<LorryState[]>([]);
  const [dcOptions, setDcOptions] = useState<DcStockContract[]>([]);
  const [skuOptions, setSkuOptions] = useState<WarehouseStockItem[]>([]);
  const [m1GeneratedAt, setM1GeneratedAt] = useState<string | null>(null);
  const [m2GeneratedAt, setM2GeneratedAt] = useState<string | null>(null);
  const [m3GeneratedAt, setM3GeneratedAt] = useState<string | null>(null);
  const [planningStartDate, setPlanningStartDate] = useState<string | null>(null);
  const [m3Locked, setM3Locked] = useState(false);
  const [m3LockReason, setM3LockReason] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function loadReferenceData() {
      setReferenceLoading(true);
      setReferenceError(null);
      try {
        const [lorryState, dcStock, warehouseStock] = await Promise.all([
          getLorryState(),
          getDcStock(),
          getWarehouseStock(),
        ]);
        if (!ignore) {
          setLorryOptions(lorryState.lorries);
          setDcOptions(dcStock.dcs);
          setSkuOptions(warehouseStock.items);
        }
      } catch (cause) {
        if (!ignore) {
          setReferenceError(cause instanceof Error ? cause.message : "Unable to load dispatch reference data.");
        }
      } finally {
        if (!ignore) {
          setReferenceLoading(false);
        }
      }
    }
    void loadReferenceData();
    return () => {
      ignore = true;
    };
  }, []);

  async function loadWorkspace(preferredPlanId?: number | null) {
    setLoadingWorkspace(true);
    setPageError(null);
    try {
      const [m1Response, m2Response, m3Response] = await Promise.all([
        getCurrentM1Results(),
        getCurrentM2Requests(),
        getCurrentM3Plans(),
      ]);

      setM1GeneratedAt(m1Response.generated_at ?? null);
      setM2GeneratedAt(m2Response.generated_at ?? null);
      setM3GeneratedAt(m3Response.generated_at ?? null);
      setPlanningStartDate(m3Response.planning_start_date ?? m1Response.planning_start_date ?? m2Response.planning_start_date ?? null);
      setM3Locked(Boolean(m3Response.locked));
      setM3LockReason(m3Response.lock_reason ?? null);
      setPlans(m3Response.plans);

      const nextSelected =
        preferredPlanId && m3Response.plans.some((plan) => plan.id === preferredPlanId)
          ? preferredPlanId
          : m3Response.plans.find((plan) => plan.is_best)?.id ?? m3Response.plans[0]?.id ?? null;
      setSelectedPlanId(nextSelected);
      if (!nextSelected) {
        setDetail(null);
        setDraftRuns([]);
      }
    } catch (cause) {
      setPageError(cause instanceof Error ? cause.message : "Unable to load current dispatch workspace.");
      setPlans([]);
      setSelectedPlanId(null);
      setDetail(null);
      setDraftRuns([]);
    } finally {
      setLoadingWorkspace(false);
    }
  }

  useEffect(() => {
    void loadWorkspace();
  }, []);

  useEffect(() => {
    let ignore = false;
    async function loadDetail(planId: number) {
      setLoadingDetail(true);
      setPageError(null);
      try {
        const response = await getCurrentM3PlanDetail(planId);
        if (!ignore) {
          setDetail(response);
          setDraftRuns(mapDetailToDraft(response));
          setValidationWarnings([]);
        }
      } catch (cause) {
        if (!ignore) {
          setPageError(cause instanceof Error ? cause.message : "Unable to load plan detail.");
          setDetail(null);
          setDraftRuns([]);
        }
      } finally {
        if (!ignore) {
          setLoadingDetail(false);
        }
      }
    }

    if (selectedPlanId) {
      void loadDetail(selectedPlanId);
    } else {
      setDetail(null);
      setDraftRuns([]);
    }
    return () => {
      ignore = true;
    };
  }, [selectedPlanId]);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) ?? null,
    [plans, selectedPlanId]
  );
  const selectedUnits = useMemo(
    () =>
      detail?.runs.reduce((sum, run) => {
        return sum + run.stops.reduce((runSum, stop) => {
          return runSum + stop.items.reduce((itemSum, item) => itemSum + item.quantity, 0);
        }, 0);
      }, 0) ?? 0,
    [detail]
  );
  const isDraftSelected = selectedPlan?.plan_status === "draft";
  const selectedPlanLabel = selectedPlan ? getPlanLabel(selectedPlan.version_number) : "Selected plan";

  function updateRun(clientId: string, updater: (current: EditableRun) => EditableRun) {
    setDraftRuns((current) => current.map((run) => (run.clientId === clientId ? updater(run) : run)));
  }
  function updateStop(runClientId: string, stopClientId: string, updater: (current: EditableStop) => EditableStop) {
    updateRun(runClientId, (run) => ({
      ...run,
      stops: run.stops.map((stop) => (stop.clientId === stopClientId ? updater(stop) : stop)),
    }));
  }
  function removeRun(clientId: string) {
    setDraftRuns((current) => current.filter((run) => run.clientId !== clientId));
  }
  function removeStop(runClientId: string, stopClientId: string) {
    updateRun(runClientId, (run) => ({
      ...run,
      stops: run.stops.filter((stop) => stop.clientId !== stopClientId),
    }));
  }
  function addRun() {
    const defaultLorry = lorryOptions[0];
    const defaultDc = dcOptions[0];
    const defaultSku = skuOptions[0];
    if (!defaultLorry || !defaultDc || !defaultSku) {
      return;
    }
    setDraftRuns((current) => [
      ...current,
      {
        clientId: makeId("run"),
        lorry_id: defaultLorry.lorry_id,
        dispatch_day: 1,
        stops: [{
          clientId: makeId("stop"),
          dc_id: defaultDc.dc_id,
          stop_sequence: 1,
          items: [{ clientId: makeId("item"), sku_id: defaultSku.sku_id, quantity: 0 }],
        }],
      },
    ]);
  }
  function addStop(runClientId: string) {
    const defaultDc = dcOptions[0];
    const defaultSku = skuOptions[0];
    if (!defaultDc || !defaultSku) {
      return;
    }
    updateRun(runClientId, (run) => ({
      ...run,
      stops: [...run.stops, {
        clientId: makeId("stop"),
        dc_id: defaultDc.dc_id,
        stop_sequence: run.stops.reduce((max, stop) => Math.max(max, stop.stop_sequence), 0) + 1,
        items: [{ clientId: makeId("item"), sku_id: defaultSku.sku_id, quantity: 0 }],
      }],
    }));
  }
  function addItem(runClientId: string, stopClientId: string) {
    const defaultSku = skuOptions[0];
    if (!defaultSku) {
      return;
    }
    updateStop(runClientId, stopClientId, (stop) => ({
      ...stop,
      items: [...stop.items, { clientId: makeId("item"), sku_id: defaultSku.sku_id, quantity: 0 }],
    }));
  }
  function removeItem(runClientId: string, stopClientId: string, itemClientId: string) {
    updateStop(runClientId, stopClientId, (stop) => ({
      ...stop,
      items: stop.items.filter((item) => item.clientId !== itemClientId),
    }));
  }

  async function handleGeneratePlan() {
    setActionLoading(true);
    setNotice(null);
    setValidationWarnings([]);
    try {
      await generatePlan();
      await loadWorkspace();
      setNotice({
        tone: "success",
        title: "Plan generated",
        message: "M2, M1, and M3 were refreshed and the live candidate set was replaced.",
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove() {
    if (!selectedPlanId) return;
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await approvePlan(selectedPlanId);
      await loadWorkspace();
      setNotice({
        tone: "success",
        title: "Plan approved",
        message: `${response.message} Reservations: ${formatInteger(response.reservations_created ?? 0)}, transfers: ${formatInteger(response.transfers_created ?? 0)}.`,
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!selectedPlanId) return;
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await rejectPlan(selectedPlanId, decisionNotes);
      await loadWorkspace();
      setNotice({ tone: "info", title: "Plan rejected", message: response.message });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleOverride() {
    if (!selectedPlanId) return;
    const payload = buildOverridePayload(draftRuns);
    if (!payload.length) {
      setNotice({ tone: "error", title: "Override payload is incomplete", message: "Add at least one run before submitting an override." });
      return;
    }
    if (payload.some((run) => !run.stops.length || run.stops.some((stop) => !stop.items.length || stop.items.some((item) => item.quantity <= 0)))) {
      setNotice({ tone: "error", title: "Override payload is incomplete", message: "Each run needs at least one stop, and each stop needs at least one item with a positive quantity." });
      return;
    }
    setActionLoading(true);
    setNotice(null);
    setValidationWarnings([]);
    try {
      const response = await overridePlan(selectedPlanId, payload, decisionNotes);
      setValidationWarnings(response.validation?.warnings ?? []);
      await loadWorkspace(selectedPlanId);
      setNotice({
        tone: "success",
        title: "Override saved",
        message: response.message + (response.validation?.warnings?.length ? " Validation warnings are shown below." : ""),
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="M3 Dispatch"
        description="Generate the live singleton plan set, compare candidate dispatches, edit overrides, and approve the final two-day lorry schedule."
        actions={
          <div className="page-actions">
            <button type="button" className="button button-primary" onClick={() => void handleGeneratePlan()} disabled={actionLoading || m3Locked}>
              {actionLoading ? "..." : "Generate Plan"}
            </button>
          </div>
        }
      />

      {loadingWorkspace || loadingDetail || referenceLoading ? <LoadingPanel label="Loading dispatch workspace..." /> : null}
      {referenceError ? <div className="notice notice-error"><p>{referenceError}</p></div> : null}
      {pageError ? <div className="notice notice-error"><p>{pageError}</p></div> : null}
      {notice ? (
        <div className={`notice notice-${notice.tone}`}>
          <h4>{notice.title}</h4>
          <p>{notice.message}</p>
          {notice.items?.length ? <ul>{notice.items.map((item) => <li key={item}>{item}</li>)}</ul> : null}
        </div>
      ) : null}
      {validationWarnings.length ? (
        <div className="notice notice-info">
          <h4>Validation warnings</h4>
          <ul>{validationWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </div>
      ) : null}

      <div className="metric-grid">
        <MetricCard label="M1 Updated" value={m1GeneratedAt ? formatDateTime(m1GeneratedAt) : "Not yet"} detail="Latest singleton priority snapshot." accent="ink" />
        <MetricCard label="M2 Updated" value={m2GeneratedAt ? formatDateTime(m2GeneratedAt) : "Not yet"} detail="Latest singleton replenishment snapshot." accent="amber" />
        <MetricCard label="M3 Updated" value={m3GeneratedAt ? formatDateTime(m3GeneratedAt) : "Not yet"} detail={planningStartDate ? `Current Day 1 starts on ${formatDate(planningStartDate)}.` : "No live dispatch generation yet."} accent="teal" />
        <MetricCard label="M3 Status" value={m3Locked ? "Locked" : "Open"} detail={m3Locked ? m3LockReason ?? "Current horizon is already approved." : "Generate Plan refreshes M2, M1, and M3 together."} accent="rose" />
      </div>

      {!loadingWorkspace && !plans.length ? (
        <EmptyState
          title={m3Locked ? "Dispatch locked for the current horizon" : "No live dispatch candidates yet"}
          description={m3Locked ? m3LockReason ?? "Generate Plan will unlock automatically on the next business day." : "Generate Plan refreshes M2, M1, and M3, then replaces the live candidate set with the latest singleton draft plans."}
        />
      ) : null}

      {plans.length ? (
        <div className="split-layout">
          <SectionCard title="Candidate Plans" description="Compare the current singleton draft candidates before selecting one.">
            <div className="plan-list">
              {plans.map((plan) => (
                <button key={plan.id} type="button" className={`plan-card${plan.id === selectedPlanId ? " plan-card-active" : ""}`} onClick={() => setSelectedPlanId(plan.id)}>
                  <div className="plan-card-header">
                    <div>
                      <h4>{getPlanLabel(plan.version_number)}</h4>
                      <p>{plan.plan_status === "draft" ? "Live candidate plan" : `Status ${plan.plan_status}`}</p>
                    </div>
                    <div className="button-row">
                      {plan.is_best ? <StatusPill value="best" tone="success" /> : null}
                      <StatusPill value={plan.plan_status} />
                    </div>
                  </div>
                  <div className="detail-list">
                    <span className="detail-chip">Score {formatNumber(plan.score ?? 0)}</span>
                    <span className="detail-chip">Runs {formatInteger(plan.run_count)}</span>
                    <span className="detail-chip">Stops {formatInteger(plan.stop_count)}</span>
                  </div>
                  <p className="subtle-text">{m3GeneratedAt ? `Updated ${formatDateTime(m3GeneratedAt)}` : "Ready for planner review."}</p>
                </button>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Selected Plan Detail" description="Review the active two-day run schedule, stop sequence, and loaded quantities.">
            {detail ? (
              <div className="panel-grid">
                <div className="cards-grid">
                  <MetricCard label="Candidate" value={selectedPlanLabel} detail={`Status ${detail.plan_status}`} accent="ink" />
                  <MetricCard label="Runs" value={formatInteger(detail.total_runs)} detail={`${formatInteger(detail.total_stops)} stops across the approved horizon.`} accent="teal" />
                  <MetricCard label="Loaded Units" value={formatInteger(selectedUnits)} detail="Total quantity carried by the selected candidate." accent="amber" />
                  <MetricCard label="Plan Score" value={formatNumber(detail.score ?? 0)} detail={detail.is_best ? "Best candidate from the current generation." : "Alternate dispatch candidate."} accent="rose" />
                </div>

                <div className="stack-list">
                  {detail.runs.map((run) => (
                    <article key={run.id} className="manifest-card">
                      <div className="manifest-card-header">
                        <div>
                          <h4>Day {run.dispatch_day}: {run.registration}</h4>
                          <p>{run.lorry_type} | capacity {formatInteger(run.capacity_units)} | {formatInteger(run.total_stops)} stops</p>
                        </div>
                        <StatusPill value={`day ${run.dispatch_day}`} tone="info" />
                      </div>
                      <div className="detail-list">
                        <span className="detail-chip">Units {formatInteger(totalRunUnits(run))}</span>
                        <span className="detail-chip">Lorry {run.registration}</span>
                      </div>
                      <div className="stack-list">
                        {run.stops.map((stop) => (
                          <div key={stop.id} className="list-card">
                            <h4>Stop {stop.stop_sequence}: {stop.dc_name}</h4>
                            <p>{stop.dc_code} | {formatInteger(stop.items.length)} SKU lines</p>
                            <div className="detail-list">
                              {stop.items.map((item) => (
                                <span key={item.id} className="detail-chip">
                                  {item.sku_code}: {formatInteger(item.quantity)}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : <p className="subtle-text">Select a plan to inspect its two-day run structure.</p>}
          </SectionCard>
        </div>
      ) : null}

      {detail ? (
        <SectionCard title="Structured Override Editor" description="Edit the full run schedule, including dispatch day, stop order, lorry assignment, and item quantities.">
          <DispatchOverrideEditor
            draftRuns={draftRuns}
            lorryOptions={lorryOptions}
            dcOptions={dcOptions}
            skuOptions={skuOptions}
            onAddRun={addRun}
            onRemoveRun={removeRun}
            onUpdateRun={updateRun}
            onUpdateStop={updateStop}
            onRemoveStop={removeStop}
            onAddStop={addStop}
            onAddItem={addItem}
            onRemoveItem={removeItem}
          />
        </SectionCard>
      ) : null}

      <SectionCard title="Planner Actions" description="Notes are reused for reject and override actions and appear in audit and report views.">
        <div className="form-field">
          <label htmlFor="decisionNotes">Planner notes</label>
          <textarea id="decisionNotes" value={decisionNotes} onChange={(event) => setDecisionNotes(event.target.value)} placeholder="Explain why this candidate was overridden or rejected." />
        </div>

        <div className="toolbar">
          <button type="button" className="button button-primary" onClick={() => void handleOverride()} disabled={!isDraftSelected || actionLoading || !detail}>Submit Override</button>
          <button type="button" className="button button-secondary" onClick={() => void handleApprove()} disabled={!isDraftSelected || actionLoading || !detail}>Approve Selected Plan</button>
          <button type="button" className="button button-danger" onClick={() => void handleReject()} disabled={!isDraftSelected || actionLoading || !detail}>Reject Selected Plan</button>
        </div>
        {!detail ? <p className="subtle-text">Select a candidate plan before taking planner actions.</p> : null}
        {detail && !isDraftSelected ? <p className="subtle-text">Actions are disabled because {selectedPlanLabel} is already {detail.plan_status}.</p> : null}
      </SectionCard>
    </div>
  );
}

export default function DispatchPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading dispatch workspace..." />}>
      <DispatchPageContent />
    </Suspense>
  );
}
