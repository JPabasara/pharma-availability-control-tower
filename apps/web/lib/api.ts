import type {
  ApprovedPlansResponse,
  ArrivalEventsResponse,
  AuditTrailResponse,
  DashboardSummary,
  DcSaleResponse,
  DcStockResponse,
  EngineRunsResponse,
  EtaResponse,
  GeneratePlanResponse,
  InputRefreshFamily,
  InputRefreshResponse,
  LorryStateContract,
  LorryAvailabilityResponse,
  M1ResultsResponse,
  M2RequestsResponse,
  M3PlanDetail,
  M3PlansResponse,
  ManifestArrivalResponse,
  ManifestUploadResponse,
  ManifestResponse,
  OpenExecutionStopsResponse,
  OverrideActionResponse,
  OverrideRunPayload,
  PlannerActionResponse,
  ReservationsResponse,
  SalesHistoryResponse,
  StockSummary,
  StopArrivalResponse,
  TransfersResponse,
  WarehouseStockContract,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

type ApiErrorDetail =
  | string
  | {
      detail?: unknown;
      message?: string;
      validation?: unknown;
      [key: string]: unknown;
    }
  | unknown;

export class ApiError extends Error {
  status: number;
  detail: ApiErrorDetail;

  constructor(message: string, status: number, detail: ApiErrorDetail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, query?: Record<string, string | number | undefined | null>) {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: ApiErrorDetail = null;
  let message = `Request failed with status ${response.status}`;

  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      detail = await response.json();
      if (typeof detail === "string") {
        message = detail;
      } else if (
        detail &&
        typeof detail === "object" &&
        "detail" in detail &&
        typeof (detail as { detail?: unknown }).detail === "string"
      ) {
        message = String((detail as { detail?: unknown }).detail);
      } else if (
        detail &&
        typeof detail === "object" &&
        "detail" in detail &&
        typeof (detail as { detail?: { message?: unknown } }).detail === "object" &&
        typeof (detail as { detail?: { message?: unknown } }).detail?.message === "string"
      ) {
        message = String((detail as { detail?: { message?: unknown } }).detail?.message);
      } else if (
        detail &&
        typeof detail === "object" &&
        "message" in detail &&
        typeof (detail as { message?: unknown }).message === "string"
      ) {
        message = String((detail as { message?: unknown }).message);
      }
    } else {
      detail = await response.text();
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      }
    }
  } catch {
    // Keep the fallback message.
  }

  return new ApiError(message, response.status, detail);
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  query?: Record<string, string | number | undefined | null>
) {
  const headers = new Headers(init?.headers ?? {});
  const hasBody = init?.body !== undefined && init?.body !== null;
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (hasBody && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildUrl(path, query), {
    cache: "no-store",
    ...init,
    headers,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

export function getDashboardSummary() {
  return apiFetch<DashboardSummary>("/api/v1/dashboard/summary");
}

export function getManifests() {
  return apiFetch<ManifestResponse>("/api/v1/inputs/manifests");
}

export function getWarehouseStock() {
  return apiFetch<WarehouseStockContract>("/api/v1/inputs/warehouse-stock");
}

export function getDcStock() {
  return apiFetch<DcStockResponse>("/api/v1/inputs/dc-stock");
}

export function getSalesHistory() {
  return apiFetch<SalesHistoryResponse>("/api/v1/inputs/sales-history");
}

export function getLorryState() {
  return apiFetch<LorryStateContract>("/api/v1/inputs/lorry-state");
}

export function getEtas() {
  return apiFetch<EtaResponse>("/api/v1/inputs/etas");
}

export function refreshAllInputs() {
  return apiFetch<InputRefreshResponse>("/api/v1/inputs/refresh-all", {
    method: "POST",
  });
}

export function refreshInputFamily(family: InputRefreshFamily) {
  return apiFetch<InputRefreshResponse>(`/api/v1/inputs/refresh/${family}`, {
    method: "POST",
  });
}

export function getEngineRuns(engineType?: "m1" | "m2" | "m3", limit = 20) {
  return apiFetch<EngineRunsResponse>("/api/v1/orchestration/runs", undefined, {
    engine_type: engineType,
    limit,
  });
}

export function generatePlan() {
  return apiFetch<GeneratePlanResponse>("/api/v1/orchestration/generate-plan", {
    method: "POST",
  });
}

export function refreshM1() {
  return apiFetch<any>("/api/v1/orchestration/refresh-m1", {
    method: "POST",
  });
}

export function refreshM2() {
  return apiFetch<any>("/api/v1/orchestration/refresh-m2", {
    method: "POST",
  });
}

export function getM1Results(runId: number) {
  return apiFetch<M1ResultsResponse>(`/api/v1/planner/m1-results/${runId}`);
}

export function getM2Requests(runId: number) {
  return apiFetch<M2RequestsResponse>(`/api/v1/planner/m2-requests/${runId}`);
}

export function getM3Plans(runId: number) {
  return apiFetch<M3PlansResponse>(`/api/v1/planner/m3-plans/${runId}`);
}

export function getM3PlanDetail(runId: number, versionId: number) {
  return apiFetch<M3PlanDetail>(`/api/v1/planner/m3-plans/${runId}/${versionId}`);
}

export function approvePlan(planVersionId: number) {
  return apiFetch<PlannerActionResponse>(`/api/v1/planner/approve/${planVersionId}`, {
    method: "POST",
  });
}

export function rejectPlan(planVersionId: number, notes: string) {
  return apiFetch<PlannerActionResponse>(`/api/v1/planner/reject/${planVersionId}`, {
    method: "POST",
    body: JSON.stringify({ notes, rejected_by: "planner-ui" }),
  });
}

export function overridePlan(planVersionId: number, changes: OverrideRunPayload[], notes: string) {
  return apiFetch<OverrideActionResponse>(`/api/v1/planner/override/${planVersionId}`, {
    method: "POST",
    body: JSON.stringify({
      changes,
      notes,
      override_by: "planner-ui",
    }),
  });
}

export function getApprovedPlans() {
  return apiFetch<ApprovedPlansResponse>("/api/v1/reports/approved-plans");
}

export function getAuditTrail(limit = 100) {
  return apiFetch<AuditTrailResponse>("/api/v1/reports/audit-trail", undefined, { limit });
}

export function getReservations() {
  return apiFetch<ReservationsResponse>("/api/v1/demo-state/reservations");
}

export function getTransfers() {
  return apiFetch<TransfersResponse>("/api/v1/demo-state/transfers");
}

export function getStockSummary() {
  return apiFetch<StockSummary>("/api/v1/demo-state/stock-summary");
}

export function getArrivalEvents() {
  return apiFetch<ArrivalEventsResponse>("/api/v1/demo-state/arrival-events");
}

export function uploadManifest(formData: FormData) {
  return apiFetch<ManifestUploadResponse>("/api/v1/demo-operations/manifests/upload", {
    method: "POST",
    body: formData,
  });
}

export function arriveManifest(manifestId: number) {
  return apiFetch<ManifestArrivalResponse>(`/api/v1/demo-operations/manifests/${manifestId}/arrive`, {
    method: "POST",
  });
}

export function postDcSale(dc_id: number, sku_id: number, quantity: number) {
  return apiFetch<DcSaleResponse>("/api/v1/demo-operations/dc-sales", {
    method: "POST",
    body: JSON.stringify({ dc_id, sku_id, quantity, actor: "planner-ui" }),
  });
}

export function getLorryHorizon() {
  return apiFetch<LorryStateContract>("/api/v1/demo-operations/lorries/horizon");
}

export function setLorryAvailability(
  lorryId: number,
  dispatch_day: number,
  status: "available" | "unavailable"
) {
  return apiFetch<LorryAvailabilityResponse>(`/api/v1/demo-operations/lorries/${lorryId}/availability`, {
    method: "POST",
    body: JSON.stringify({ dispatch_day, status, actor: "planner-ui" }),
  });
}

export function getOpenExecutionStops() {
  return apiFetch<OpenExecutionStopsResponse>("/api/v1/demo-operations/execution/open-stops");
}

export function arriveExecutionStop(planStopId: number) {
  return apiFetch<StopArrivalResponse>(`/api/v1/demo-operations/execution/stops/${planStopId}/arrive`, {
    method: "POST",
  });
}
