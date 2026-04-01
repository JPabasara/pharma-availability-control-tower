export type EngineType = "m1" | "m2" | "m3";

export type RunContext = {
  m1RunId: number | null;
  m2RunId: number | null;
  m3RunId: number | null;
  generatedAt: string | null;
};

export type DashboardAlert = {
  type: string;
  severity: "critical" | "warning" | "info" | "low" | "medium" | "high";
  message: string;
  dc_id?: number;
  details?: Array<Record<string, string | number>>;
};

export type DashboardSummary = {
  pending_approvals: number;
  approved_plans: number;
  active_manifests: number;
  latest_engine_run: EngineRunSummary | null;
  fleet_status: {
    total: number;
    available: number;
    unavailable: number;
    reefer_available: number;
    normal_available: number;
  };
  alerts: DashboardAlert[];
  alert_count: number;
};

export type ManifestLine = {
  manifest_line_id: number;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  quantity: number;
  reefer_required: boolean;
};

export type ManifestContract = {
  manifest_snapshot_id: number;
  manifest_name: string;
  vessel_id: number;
  vessel_name: string;
  vessel_code: string;
  status: string;
  snapshot_time: string;
  lines: ManifestLine[];
};

export type ManifestResponse = {
  manifests: ManifestContract[];
  count: number;
};

export type WarehouseStockItem = {
  sku_id: number;
  sku_code: string;
  sku_name: string;
  reefer_required: boolean;
  physical: number;
  reserved: number;
  effective: number;
};

export type WarehouseStockContract = {
  snapshot_id: number;
  snapshot_time: string;
  items: WarehouseStockItem[];
};

export type DcStockItem = {
  sku_id: number;
  sku_code: string;
  sku_name: string;
  physical: number;
  in_transit: number;
  effective: number;
};

export type DcStockContract = {
  dc_id: number;
  dc_code: string;
  dc_name: string;
  snapshot_id: number;
  snapshot_time: string;
  items: DcStockItem[];
};

export type DcStockResponse = {
  dcs: DcStockContract[];
  count: number;
};

export type SalesForecast = {
  dc_id: number;
  dc_code: string;
  dc_name: string;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  total_sold_30d: number;
  lookback_days: number;
  daily_avg: number;
  forecast_48h: number;
};

export type SalesHistoryResponse = {
  forecasts: SalesForecast[];
  count: number;
};

export type LorryDayState = {
  dispatch_day: number;
  business_date: string;
  status: string;
  source: string;
};

export type LorryState = {
  lorry_id: number;
  registration: string;
  lorry_type: "normal" | "reefer" | string;
  capacity_units: number;
  status: string;
  day1_status: string;
  day2_status: string;
  day_states: LorryDayState[];
};

export type LorryStateContract = {
  snapshot_id: number;
  snapshot_time: string;
  planning_dates: string[];
  lorries: LorryState[];
};

export type EtaRecord = {
  vessel_id: number;
  vessel_name: string;
  vessel_code: string;
  eta_time: string;
  fetched_at: string;
  hours_until_arrival: number;
  source: string;
};

export type EtaResponse = {
  etas: EtaRecord[];
  count: number;
};

export type EngineRunSummary = {
  id: number;
  engine_type: EngineType;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  input_snapshot_ids?: Record<string, unknown> | null;
};

export type EngineRunsResponse = {
  runs: EngineRunSummary[];
  count: number;
};

export type M1LineResult = {
  id: number;
  manifest_line_id: number;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  priority_score: number;
  priority_band: "critical" | "high" | "medium" | "low";
  reefer_required: boolean;
};

export type M1SkuSummary = {
  sku_id: number;
  sku_code: string;
  sku_name: string;
  reefer_required: boolean;
  avg_score: number;
  max_score: number;
  line_count: number;
  highest_band: "critical" | "high" | "medium" | "low";
};

export type M1ResultsResponse = {
  run_id: number;
  status: string;
  line_results: M1LineResult[];
  sku_summary: M1SkuSummary[];
  total_lines: number;
};

export type M2Request = {
  id: number;
  dc_id: number;
  dc_code: string;
  dc_name: string;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  requested_quantity: number;
  urgency: "critical" | "high" | "medium" | "low";
  required_by: string | null;
};

export type M2RequestsResponse = {
  run_id: number;
  status: string;
  requests: M2Request[];
  total_requests: number;
};

export type M3PlanSummary = {
  id: number;
  version_number: number;
  plan_status: "draft" | "approved" | "rejected" | string;
  score: number | null;
  is_best: boolean;
  approved_at: string | null;
  approved_by: string | null;
  run_count: number;
  stop_count: number;
};

export type M3PlansResponse = {
  run_id: number;
  status: string;
  plans: M3PlanSummary[];
  total_plans: number;
};

export type M3PlanItem = {
  id: number;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  quantity: number;
};

export type M3PlanStop = {
  id: number;
  stop_sequence: number;
  dc_id: number;
  dc_code: string;
  dc_name: string;
  items: M3PlanItem[];
};

export type M3PlanFlatStop = M3PlanStop & {
  lorry_id: number;
  registration: string;
  lorry_type: string;
  capacity_units: number;
  dispatch_day: number;
};

export type M3PlanRun = {
  id: number;
  lorry_id: number;
  registration: string;
  lorry_type: string;
  capacity_units: number;
  dispatch_day: number;
  stops: M3PlanStop[];
  total_stops: number;
};

export type M3PlanDetail = {
  id: number;
  run_id: number;
  version_number: number;
  plan_status: "draft" | "approved" | "rejected" | string;
  score: number | null;
  is_best: boolean;
  approved_at: string | null;
  approved_by: string | null;
  runs: M3PlanRun[];
  stops: M3PlanFlatStop[];
  total_runs: number;
  total_stops: number;
  total_items: number;
};

export type OverrideValidation = {
  valid: boolean;
  errors: string[];
  warnings: string[];
};

export type OverrideActionResponse = {
  success: boolean;
  message: string;
  new_plan_version_id?: number;
  new_version_number?: number;
  validation?: OverrideValidation;
};

export type PlannerActionResponse = {
  success: boolean;
  message: string;
  plan_version_id?: number;
  reservations_created?: number;
  transfers_created?: number;
};

export type GeneratePlanResponse = {
  success: boolean;
  message: string;
  orchestration_time: string;
  m2_run_id: number;
  m1_run_id: number;
  m3_run_id: number;
  m2_requests_count: number;
  m1_results_count: number;
  m3_plans_count: number;
};

export type OverrideStopPayload = {
  dc_id: number;
  stop_sequence: number;
  items: Array<{
    sku_id: number;
    quantity: number;
  }>;
};

export type OverrideRunPayload = {
  lorry_id: number;
  dispatch_day: number;
  stops: OverrideStopPayload[];
};

export type ApprovedPlanDecision = {
  id: number;
  decision_type: string;
  decided_at: string | null;
  decided_by: string;
  notes: string | null;
  override_reasons?: Array<{
    field_changed: string;
    old_value: string;
    new_value: string;
    reason: string | null;
  }>;
};

export type ApprovedPlan = {
  id: number;
  engine_run_id: number;
  version_number: number;
  score: number | null;
  approved_at: string | null;
  approved_by: string | null;
  runs: Array<{
    id: number;
    lorry_id: number;
    registration: string;
    lorry_type: string;
    dispatch_day: number;
    stops: Array<{
      id: number;
      stop_sequence: number;
      dc_id: number;
      dc_code: string;
      dc_name: string;
      items: Array<{
        sku_id: number;
        sku_code: string;
        sku_name: string;
        quantity: number;
      }>;
    }>;
  }>;
  stops: Array<{
    id: number;
    lorry_id: number;
    registration: string;
    lorry_type: string;
    dispatch_day: number;
    stop_sequence: number;
    dc_id: number;
    dc_code: string;
    dc_name: string;
    items: Array<{
      sku_id: number;
      sku_code: string;
      sku_name: string;
      quantity: number;
    }>;
  }>;
  decisions: ApprovedPlanDecision[];
};

export type ApprovedPlansResponse = {
  approved_plans: ApprovedPlan[];
  count: number;
};

export type AuditEntry = {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  actor: string;
  timestamp: string | null;
  details: Record<string, unknown> | null;
};

export type AuditTrailResponse = {
  audit_trail: AuditEntry[];
  count: number;
};

export type DemoReservation = {
  id: number;
  plan_version_id: number;
  plan_stop_id: number | null;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  quantity_reserved: number;
  status: string;
  created_at: string | null;
};

export type ReservationsResponse = {
  reservations: DemoReservation[];
  count: number;
};

export type DemoTransfer = {
  id: number;
  plan_version_id: number;
  plan_stop_id: number | null;
  lorry_id: number;
  registration: string;
  lorry_type: string;
  dc_id: number;
  dc_code: string;
  dc_name: string;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  quantity: number;
  dispatch_day: number | null;
  stop_sequence: number | null;
  status: string;
  dispatched_at: string | null;
  arrived_at: string | null;
};

export type TransfersResponse = {
  transfers: DemoTransfer[];
  count: number;
};

export type StockSummary = {
  warehouse: WarehouseStockContract;
  dcs: DcStockContract[];
  totals: {
    total_wh_physical: number;
    total_wh_reserved: number;
    total_wh_effective: number;
    total_dc_physical: number;
    total_dc_in_transit: number;
    total_dc_effective: number;
  };
};

export type ArrivalEvent = {
  id: number;
  event_type: string;
  reference_id: number;
  event_time: string | null;
  details: Record<string, unknown> | null;
};

export type ArrivalEventsResponse = {
  events: ArrivalEvent[];
  count: number;
};

export type ManifestUploadResponse = {
  success: boolean;
  message: string;
  manifest_id: number;
  line_count: number;
};

export type ManifestArrivalResponse = {
  success: boolean;
  message: string;
  arrived: number;
  manifest_id: number;
  total_skus_updated: number;
  total_quantity_added: number;
};

export type DcSaleResponse = {
  success: boolean;
  message: string;
  dc_id: number;
  sku_id: number;
  quantity_sold: number;
};

export type LorryAvailabilityResponse = {
  success: boolean;
  message: string;
  lorry_id: number;
  status: string;
  business_dates: string[];
};

export type OpenExecutionStop = {
  plan_stop_id: number;
  plan_version_id: number;
  plan_run_id: number;
  dispatch_day: number;
  lorry_id: number;
  registration: string;
  lorry_type: string;
  dc_id: number;
  dc_code: string;
  dc_name: string;
  stop_sequence: number;
  items: Array<{
    transfer_id: number;
    sku_id: number;
    sku_code: string;
    sku_name: string;
    quantity: number;
  }>;
};

export type OpenExecutionStopsResponse = {
  open_stops: OpenExecutionStop[];
  count: number;
};

export type StopArrivalResponse = {
  success: boolean;
  message: string;
  plan_stop_id: number;
  transfers_arrived: number;
  reservations_released: number;
  total_quantity_moved: number;
};
