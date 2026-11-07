// Shapes of the Python API (api/main.py) and the model contract (docs/inputs_and_contract.md).

export type Wildfire = {
  score: number | null;
  rating: string;
  p_fire_annual: number;
  level: "tract" | "zip" | "hazard_zone_only";
  tract_geoid?: string;
  method: string;
  stub: boolean;
  components: {
    very_high_hazard_pct?: number;
    high_hazard_pct?: number;
    burned_footprint_pct?: number;
    fires_since_2015?: number;
    last_fire_year?: number | null;
    fema_expected_annual_loss?: number | null;
  };
};

export type Area = {
  address?: string;
  geocode?: { matched_address: string; zip: string; tract_geoid: string; lat: number; lon: number };
  hazard_class?: string | null;
  fair_plan_share?: number | null;
  fires_within_5km?: { fire_name: string | null; year: number | null; distance_km: number }[];
  zip_home_value?: number | null;
  zip_insurance_trend?: { year: number; nonrenewal_rate: number | null }[];
  wildfire?: Wildfire;
};

export type Insurance = {
  documents: string[];
  has_dic: boolean;
  dwelling_limit: number | null;
  dwelling_settlement: "replacement_cost" | "actual_cash_value" | "unknown" | null;
  extended_replacement_pct: number | null;
  premium_total: number | null;
  liability_limit: number | null;
  loss_of_use_limit: number | null;
  code_upgrade: boolean;
  debris_removal: boolean;
};

export type Inputs = {
  address: string;
  home: Record<string, string | number | null>;
  measures_done: string[];
  insurance: Insurance;
  budget: number;
};

export type Fix = {
  measure_id: string;
  name: string;
  cost_low: number;
  cost_high: number;
  impact_after: number;
  est_annual_benefit: number;
  est_premium_saving: number;
  est_avoided_loss: number;
  payback_years: number | null;
  within_budget: boolean;
  why: string;
};

export type Gap = { gap: string; severity: "high" | "medium" | "low"; why: string };

export type Range = { low: number; high: number };
export type Coverage = {
  scope_note: string;
  components: { name: string; cost: Range; payout: Range; shortfall: Range; notes: string[] }[];
  total_cost: Range;
  total_payout: Range;
  total_shortfall: Range;
};

export type Result = {
  current: {
    wildfire: Wildfire;
    house: { impact: number; rating: string };
    insurance_gap: Gap[];
    coverage?: Coverage | null;
  };
  future: {
    fixes: Fix[];
    plan_within_budget: string[];
    plan_cost_low: number;
    house_after_plan: { impact: number; rating: string };
  };
  caveats: string[];
  sources: { wildfire: string; house: string };
};

export type ExtractedField = {
  field: string;
  label: string;
  must_have: boolean;
  value: unknown;
  source_text: string | null;
  page: number | null;
  verified: boolean | null;
  flag?: string;
};

export type Extraction = {
  documents: { file: string; source: string; text_layer: boolean; fields: ExtractedField[] }[];
  merged: Record<string, unknown> & { documents: string[]; has_dic: boolean };
};

export type Scenario = {
  title: string;
  description: string;
  address: string;
  home: Record<string, string | number>;
  measures_done: string[];
  insurance: Omit<Insurance, "documents" | "has_dic"> & { type: string };
  budget: number;
};

export type Health = { ok: boolean; ai_enabled: boolean; sources: { wildfire: string; house: string } };
