"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  ApiError,
  approvePlan,
  generatePlan,
  refreshM1,
  refreshM2,
  getDcStock,
  getLorryState,
  getM3PlanDetail,
  getM3Plans,
  getWarehouseStock,
  overridePlan,
  rejectPlan,
} from "@/lib/api";
import { formatDateTime, formatInteger, formatNumber, getPlanLabel } from "@/lib/format";
import { usePlannerRunContext, useResolvedRunId } from "@/lib/run-context";
import type {
  DcStockContract,
  LorryState,
  M3PlanDetail,
  M3PlanSummary,
  OverrideRunPayload,
  WarehouseStockItem,
} from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { LoadingPanel } from "@/components/LoadingPanel";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusPill } from "@/components/StatusPill";

type EditableItem = { clientId: string; sku_id: number; quantity: number };
type EditableStop = { clientId: string; dc_id: number; stop_sequence: number; items: EditableItem[] };
type EditableRun = { clientId: string; lorry_id: number; dispatch_day: number; stops: EditableStop[] };
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

function describeLorry(lorry: LorryState) {
  return `${lorry.registration} | ${lorry.lorry_type} | cap ${lorry.capacity_units} | D1 ${lorry.day1_status} | D2 ${lorry.day2_status}`;
}

function totalRunUnits(run: { stops: Array<{ items: Array<{ quantity: number }> }> }) {
  return run.stops.reduce(
    (sum, stop) => sum + stop.items.reduce((itemSum, item) => itemSum + item.quantity, 0),
    0
  );
}

function DispatchPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const { runContext, setRunContext } = usePlannerRunContext();
  const { runId, loading: runLoading, error: runError } = useResolvedRunId("m3");
  const [plans, setPlans] = useState<M3PlanSummary[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [detail, setDetail] = useState<M3PlanDetail | null>(null);
  const [draftRuns, setDraftRuns] = useState<EditableRun[]>([]);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [referenceLoading, setReferenceLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [lorryOptions, setLorryOptions] = useState<LorryState[]>([]);
  const [dcOptions, setDcOptions] = useState<DcStockContract[]>([]);
  const [skuOptions, setSkuOptions] = useState<WarehouseStockItem[]>([]);

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
          setReferenceError(
            cause instanceof Error ? cause.message : "Unable to load dispatch reference data."
          );
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

  useEffect(() => {
    let ignore = false;
    async function loadPlans(activeRunId: number, preferredPlanId?: number | null) {
      setLoadingPlans(true);
      setPageError(null);
      try {
        const response = await getM3Plans(activeRunId);
        if (ignore) {
          return;
        }
        setPlans(response.plans);
        const selected =
          preferredPlanId ??
          response.plans.find((plan) => plan.id === selectedPlanId)?.id ??
          response.plans.find((plan) => plan.is_best)?.id ??
          response.plans[0]?.id ??
          null;
        setSelectedPlanId(selected);
      } catch (cause) {
        if (!ignore) {
          setPageError(cause instanceof Error ? cause.message : "Unable to load candidate plans.");
          setPlans([]);
          setSelectedPlanId(null);
        }
      } finally {
        if (!ignore) {
          setLoadingPlans(false);
        }
      }
    }
    if (runId) {
      void loadPlans(runId);
    } else {
      setPlans([]);
      setSelectedPlanId(null);
    }
    return () => {
      ignore = true;
    };
  }, [runId, selectedPlanId]);

  useEffect(() => {
    let ignore = false;
    async function loadDetail(activeRunId: number, planId: number) {
      setLoadingDetail(true);
      setPageError(null);
      try {
        const response = await getM3PlanDetail(activeRunId, planId);
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
    if (runId && selectedPlanId) {
      void loadDetail(runId, selectedPlanId);
    } else {
      setDetail(null);
      setDraftRuns([]);
    }
    return () => {
      ignore = true;
    };
  }, [runId, selectedPlanId]);

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

  function updateRunContextPart(updates: Partial<import("@/lib/types").RunContext>) {
    const nextContext = {
      m1RunId: null,
      m2RunId: null,
      m3RunId: null,
      generatedAt: null,
      ...runContext,
      ...updates,
    };
    setRunContext(nextContext);

    const params = new URLSearchParams(window.location.search);
    if (nextContext.m1RunId) params.set("m1RunId", String(nextContext.m1RunId));
    if (nextContext.m2RunId) params.set("m2RunId", String(nextContext.m2RunId));
    if (nextContext.m3RunId) params.set("m3RunId", String(nextContext.m3RunId));
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

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
        stops: [
          {
            clientId: makeId("stop"),
            dc_id: defaultDc.dc_id,
            stop_sequence: 1,
            items: [{ clientId: makeId("item"), sku_id: defaultSku.sku_id, quantity: 0 }],
          },
        ],
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
      stops: [
        ...run.stops,
        {
          clientId: makeId("stop"),
          dc_id: defaultDc.dc_id,
          stop_sequence: run.stops.reduce((max, stop) => Math.max(max, stop.stop_sequence), 0) + 1,
          items: [{ clientId: makeId("item"), sku_id: defaultSku.sku_id, quantity: 0 }],
        },
      ],
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

  async function handleRefreshM1() {
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await refreshM1();
      updateRunContextPart({ m1RunId: response.m1_run_id, m1GeneratedAt: response.orchestration_time });
      setNotice({
        tone: "success",
        title: "M1 Refreshed",
        message: `Generated M1 run #${response.m1_run_id}.`,
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRefreshM2() {
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await refreshM2();
      updateRunContextPart({ m2RunId: response.m2_run_id, m2GeneratedAt: response.orchestration_time });
      setNotice({
        tone: "success",
        title: "M2 Refreshed",
        message: `Generated M2 run #${response.m2_run_id}.`,
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleGeneratePlan() {
    setActionLoading(true);
    setNotice(null);
    setValidationWarnings([]);
    try {
      const response = await generatePlan();
      updateRunContextPart({ m3RunId: response.m3_run_id, generatedAt: response.orchestration_time });
      setNotice({
        tone: "success",
        title: "Plan generated",
        message: `Created M3 run #${response.m3_run_id}.`,
      });
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove() {
    if (!selectedPlanId || !runId) {
      return;
    }
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await approvePlan(selectedPlanId);
      setNotice({
        tone: "success",
        title: "Plan approved",
        message:
          `${response.message} ` +
          `Reservations: ${formatInteger(response.reservations_created ?? 0)}, transfers: ${formatInteger(response.transfers_created ?? 0)}.`,
      });
      const latestPlans = await getM3Plans(runId);
      setPlans(latestPlans.plans);
      const refreshed = await getM3PlanDetail(runId, selectedPlanId);
      setDetail(refreshed);
      setDraftRuns(mapDetailToDraft(refreshed));
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!selectedPlanId || !runId) {
      return;
    }
    setActionLoading(true);
    setNotice(null);
    try {
      const response = await rejectPlan(selectedPlanId, decisionNotes);
      setNotice({ tone: "info", title: "Plan rejected", message: response.message });
      const latestPlans = await getM3Plans(runId);
      setPlans(latestPlans.plans);
      const refreshed = await getM3PlanDetail(runId, selectedPlanId);
      setDetail(refreshed);
      setDraftRuns(mapDetailToDraft(refreshed));
    } catch (cause) {
      setNotice(parseApiError(cause));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleOverride() {
    if (!selectedPlanId || !runId) {
      return;
    }
    const payload = buildOverridePayload(draftRuns);
    if (!payload.length) {
      setNotice({
        tone: "error",
        title: "Override payload is incomplete",
        message: "Add at least one run before submitting an override.",
      });
      return;
    }
    if (
      payload.some(
        (run) =>
          !run.stops.length ||
          run.stops.some((stop) => !stop.items.length || stop.items.some((item) => item.quantity <= 0))
      )
    ) {
      setNotice({
        tone: "error",
        title: "Override payload is incomplete",
        message: "Each run needs at least one stop, and each stop needs at least one item with a positive quantity.",
      });
      return;
    }
    setActionLoading(true);
    setNotice(null);
    setValidationWarnings([]);
    try {
      const response = await overridePlan(selectedPlanId, payload, decisionNotes);
      setValidationWarnings(response.validation?.warnings ?? []);
      setNotice({
        tone: "success",
        title: "Override created",
        message:
          response.message +
          (response.validation?.warnings?.length ? " Validation warnings are shown below." : ""),
      });
      const latestPlans = await getM3Plans(runId);
      setPlans(latestPlans.plans);
      const nextPlanId =
        response.new_plan_version_id ??
        latestPlans.plans[latestPlans.plans.length - 1]?.id ??
        selectedPlanId;
      setSelectedPlanId(nextPlanId);
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
        description="Generate plans, compare candidate dispatches, edit run-based overrides, and approve the final two-day lorry schedule."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void handleRefreshM1()}
              disabled={actionLoading}
            >
              {actionLoading ? "..." : "Refresh M1"}
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void handleRefreshM2()}
              disabled={actionLoading}
            >
              {actionLoading ? "..." : "Refresh M2"}
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={() => void handleGeneratePlan()}
              disabled={actionLoading}
            >
              {actionLoading ? "..." : "Generate Plan"}
            </button>
          </div>
        }
      />

      {runLoading || referenceLoading || loadingPlans || loadingDetail ? <LoadingPanel label="Loading dispatch workspace..." /> : null}
      {runError ? <div className="notice notice-error"><p>{runError}</p></div> : null}
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

      {runContext?.m1RunId || runContext?.m2RunId || runContext?.m3RunId ? (
        <div className="metric-grid">
          <MetricCard 
            label="M1 Run" 
            value={runContext?.m1RunId ? `#${runContext.m1RunId}` : "None"} 
            detail={runContext?.m1GeneratedAt ? `Updated ${formatDateTime(runContext.m1GeneratedAt)}` : "Priority results linked into the current planner session."} 
            accent="ink" 
          />
          <MetricCard 
            label="M2 Run" 
            value={runContext?.m2RunId ? `#${runContext.m2RunId}` : "None"} 
            detail={runContext?.m2GeneratedAt ? `Updated ${formatDateTime(runContext.m2GeneratedAt)}` : "Request generation context preserved across page refreshes."} 
            accent="amber" 
          />
          <MetricCard 
            label="M3 Run" 
            value={runContext?.m3RunId ? `#${runContext.m3RunId}` : "None"} 
            detail="Candidate plan set currently active in Dispatch." 
            accent="teal" 
          />
          <MetricCard 
            label="M3 Generated" 
            value={runContext?.generatedAt ? formatDateTime(runContext.generatedAt).split(" ")[1] ?? "Time" : "Not yet"} 
            detail={runContext?.generatedAt ? formatDateTime(runContext.generatedAt).split(" ")[0] ?? "Date" : "Stored in local run context after Generate Plan."} 
            accent="rose" 
          />
        </div>
      ) : null}

      {!runLoading && !runId ? (
        <EmptyState
          title="No dispatch run yet"
          description="The seeded environment is ready. Generate a plan to create M1, M2, and M3 runs and unlock the planner workflow."
        />
      ) : null}

      {plans.length ? (
        <div className="split-layout">
          <SectionCard title="Candidate Plans" description="Compare score, day allocation, and stop counts before selecting one.">
            <div className="plan-list">
              {plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  className={`plan-card${plan.id === selectedPlanId ? " plan-card-active" : ""}`}
                  onClick={() => setSelectedPlanId(plan.id)}
                >
                  <div className="plan-card-header">
                    <div>
                      <h4>{getPlanLabel(plan.version_number)}</h4>
                      <p>Version #{plan.version_number}</p>
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
                  <p className="subtle-text">Approved {formatDateTime(plan.approved_at)}</p>
                </button>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Selected Plan Detail" description="Review the active two-day run schedule, stop sequence, and loaded quantities.">
            {detail ? (
              <div className="panel-grid">
                <div className="cards-grid">
                  <MetricCard label="Version" value={`#${detail.version_number}`} detail={`Status ${detail.plan_status}`} accent="ink" />
                  <MetricCard label="Runs" value={formatInteger(detail.total_runs)} detail={`${formatInteger(detail.total_stops)} stops across the approved horizon.`} accent="teal" />
                  <MetricCard label="Loaded Units" value={formatInteger(selectedUnits)} detail="Total quantity carried by the selected version." accent="amber" />
                  <MetricCard label="Plan Score" value={formatNumber(detail.score ?? 0)} detail={detail.is_best ? "Best candidate from the current run." : "Alternate dispatch candidate."} accent="rose" />
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
                        <span className="detail-chip">Lorry #{run.lorry_id}</span>
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
        <SectionCard
          title="Structured Override Editor"
          description="Edit the full run schedule, including dispatch day, stop order, lorry assignment, and item quantities."
          actions={
            <div className="section-card-actions">
              <button type="button" className="button button-secondary" onClick={addRun}>
                Add Run
              </button>
            </div>
          }
        >
          <div className="editor-grid">
            {draftRuns.map((run) => {
              const selectedLorry = lorryOptions.find((lorry) => lorry.lorry_id === run.lorry_id);
              return (
                <article key={run.clientId} className="editor-run">
                  <div className="editor-run-header">
                    <div>
                      <h4>Editable Run</h4>
                      <p className="subtle-text">Dispatch day and lorry assignment are part of the override payload.</p>
                    </div>
                    <button type="button" className="button button-ghost" onClick={() => removeRun(run.clientId)}>
                      Remove Run
                    </button>
                  </div>

                  <div className="field-grid">
                    <div className="form-field">
                      <label htmlFor={`${run.clientId}-lorry`}>Lorry</label>
                      <select
                        id={`${run.clientId}-lorry`}
                        value={run.lorry_id}
                        onChange={(event) =>
                          updateRun(run.clientId, (current) => ({ ...current, lorry_id: Number(event.target.value) }))
                        }
                      >
                        {lorryOptions.map((lorry) => (
                          <option key={lorry.lorry_id} value={lorry.lorry_id}>
                            {describeLorry(lorry)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-field">
                      <label htmlFor={`${run.clientId}-day`}>Dispatch Day</label>
                      <select
                        id={`${run.clientId}-day`}
                        value={run.dispatch_day}
                        onChange={(event) =>
                          updateRun(run.clientId, (current) => ({ ...current, dispatch_day: Number(event.target.value) }))
                        }
                      >
                        <option value={1}>Day 1</option>
                        <option value={2}>Day 2</option>
                      </select>
                    </div>
                  </div>

                  {selectedLorry ? (
                    <p className="subtle-text">
                      Horizon status: Day 1 {selectedLorry.day1_status}, Day 2 {selectedLorry.day2_status}.
                    </p>
                  ) : null}

                  <div className="stack-list">
                    {run.stops.map((stop) => (
                      <article key={stop.clientId} className="editor-stop">
                        <div className="editor-stop-header">
                          <div>
                            <h4>Stop Payload</h4>
                            <p className="subtle-text">Each run may contain up to two DC stops after validation.</p>
                          </div>
                          <button type="button" className="button button-ghost" onClick={() => removeStop(run.clientId, stop.clientId)}>
                            Remove Stop
                          </button>
                        </div>

                        <div className="field-grid">
                          <div className="form-field">
                            <label htmlFor={`${stop.clientId}-dc`}>Distribution Center</label>
                            <select
                              id={`${stop.clientId}-dc`}
                              value={stop.dc_id}
                              onChange={(event) =>
                                updateStop(run.clientId, stop.clientId, (current) => ({ ...current, dc_id: Number(event.target.value) }))
                              }
                            >
                              {dcOptions.map((dc) => (
                                <option key={dc.dc_id} value={dc.dc_id}>
                                  {dc.dc_code} - {dc.dc_name}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="form-field">
                            <label htmlFor={`${stop.clientId}-sequence`}>Stop Sequence</label>
                            <input
                              id={`${stop.clientId}-sequence`}
                              type="number"
                              min={1}
                              value={stop.stop_sequence}
                              onChange={(event) =>
                                updateStop(run.clientId, stop.clientId, (current) => ({ ...current, stop_sequence: Number(event.target.value) }))
                              }
                            />
                          </div>
                        </div>

                        <div className="items-list">
                          {stop.items.map((item) => (
                            <div key={item.clientId} className="item-row">
                              <div className="form-field">
                                <label htmlFor={`${item.clientId}-sku`}>SKU</label>
                                <select
                                  id={`${item.clientId}-sku`}
                                  value={item.sku_id}
                                  onChange={(event) =>
                                    updateStop(run.clientId, stop.clientId, (current) => ({
                                      ...current,
                                      items: current.items.map((currentItem) =>
                                        currentItem.clientId === item.clientId
                                          ? { ...currentItem, sku_id: Number(event.target.value) }
                                          : currentItem
                                      ),
                                    }))
                                  }
                                >
                                  {skuOptions.map((sku) => (
                                    <option key={sku.sku_id} value={sku.sku_id}>
                                      {sku.sku_code} - {sku.sku_name}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div className="form-field">
                                <label htmlFor={`${item.clientId}-qty`}>Quantity</label>
                                <input
                                  id={`${item.clientId}-qty`}
                                  type="number"
                                  min={0}
                                  value={item.quantity}
                                  onChange={(event) =>
                                    updateStop(run.clientId, stop.clientId, (current) => ({
                                      ...current,
                                      items: current.items.map((currentItem) =>
                                        currentItem.clientId === item.clientId
                                          ? { ...currentItem, quantity: Number(event.target.value) }
                                          : currentItem
                                      ),
                                    }))
                                  }
                                />
                              </div>

                              <button type="button" className="button button-ghost" onClick={() => removeItem(run.clientId, stop.clientId, item.clientId)}>
                                Remove Item
                              </button>
                            </div>
                          ))}
                        </div>

                        <div className="toolbar">
                          <button type="button" className="button button-secondary" onClick={() => addItem(run.clientId, stop.clientId)}>
                            Add Item
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>

                  <div className="toolbar">
                    <button type="button" className="button button-secondary" onClick={() => addStop(run.clientId)}>
                      Add Stop
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Planner Actions"
        description="Notes are reused for reject and override actions and appear in audit and report views."
      >
        <div className="form-field">
          <label htmlFor="decisionNotes">Planner notes</label>
          <textarea
            id="decisionNotes"
            value={decisionNotes}
            onChange={(event) => setDecisionNotes(event.target.value)}
            placeholder="Explain why this version was overridden or rejected."
          />
        </div>

        <div className="toolbar">
          <button type="button" className="button button-primary" onClick={() => void handleOverride()} disabled={!isDraftSelected || actionLoading || !detail}>
            Submit Override
          </button>
          <button type="button" className="button button-secondary" onClick={() => void handleApprove()} disabled={!isDraftSelected || actionLoading || !detail}>
            Approve Selected Plan
          </button>
          <button type="button" className="button button-danger" onClick={() => void handleReject()} disabled={!isDraftSelected || actionLoading || !detail}>
            Reject Selected Plan
          </button>
        </div>
        {!detail ? <p className="subtle-text">Select a candidate plan before taking planner actions.</p> : null}
        {detail && !isDraftSelected ? (
          <p className="subtle-text">
            Actions are disabled because plan version #{detail.version_number} is already {detail.plan_status}.
          </p>
        ) : null}
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
