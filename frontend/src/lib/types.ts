export interface PredictionFactor {
  signal: string;
  direction: "supports" | "contradicts" | "neutral";
  weight: number;
  counterfactual?: string;
}

export interface PredictionSource {
  name: string;
  platform: string;
  reliability: number;
  articles_used?: number;
  signal?: string;
}

export interface PredictionSignals {
  factors?: PredictionFactor[];
  sources?: PredictionSource[];
  method?: string;
  tools_used?: string[];
}

export interface Prediction {
  id: string;
  title: string;
  description: string;
  probability: number;
  confidence: number;
  time_horizon: "short" | "medium" | "long";
  status: "active" | "resolved" | "expired";
  source: string;
  agent_id?: string;
  agent_name?: string;
  category?: string;
  created_at: string;
  updated_at: string;
  resolution_date?: string;
  resolution?: boolean;
  tags?: string[];
  reasoning?: string;
  data_signals?: PredictionSignals;
}

export interface PredictionScore {
  id: string;
  prediction_id: string;
  brier_score: number;
  log_score: number;
  calibration_error: number;
  scored_at: string;
}

export interface Source {
  id: string;
  name: string;
  type: string;
  url?: string;
  reliability_score: number;
  active: boolean;
  last_fetched?: string;
}

export interface Agent {
  id: string;
  name: string;
  type: string;
  model?: string;
  brier_score: number;
  total_predictions: number;
  resolved_predictions: number;
  accuracy_rate: number;
  active: boolean;
  created_at: string;
  last_active?: string;
  description?: string;
}

export interface UserInterest {
  id: string;
  name: string;
  keywords: string[];
  priority: "high" | "medium" | "low";
  category: string;
  active: boolean;
  created_at: string;
  updated_at: string;
  indicators?: string[];
  market_filters?: string[];
  region?: string;
  enabled: boolean;
}

export interface EventNode {
  id: string;
  label: string;
  type: string;
  probability?: number;
  group?: string;
}

export interface EventEdge {
  source: string;
  target: string;
  weight: number;
  relationship: string;
}

export interface GraphData {
  nodes: EventNode[];
  edges: EventEdge[];
}

export interface DashboardStats {
  total_predictions: number;
  active_predictions: number;
  resolved_predictions: number;
  average_accuracy: number;
  average_brier_score: number;
  active_sources: number;
  active_agents: number;
  predictions_today: number;
  accuracy_trend: number;
}

export interface Indicator {
  id: string;
  source_agency: string;
  series_id: string;
  name: string;
  category?: string;
  region?: string;
  value: number;
  unit?: string;
  period: string;
  release_date?: string;
  created_at: string;
}

export interface IndicatorHistory {
  series_id: string;
  agency: string;
  name: string;
  unit?: string;
  data: { period: string; value: number; release_date?: string }[];
}

export interface Insight {
  id: string;
  created_at: string;
  domain: string;
  title: string;
  ground_truth: string;
  trend_analysis: string;
  prediction: string;
  action_items?: string[];
  confidence: string;
  sources?: {
    indicators?: string[];
    market_sources?: string[];
    news_sources?: string[];
  };
  stale: boolean;
}

export interface ApiResponse<T> {
  data: T;
  status: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
