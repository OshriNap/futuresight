import {
  Prediction,
  Agent,
  UserInterest,
  DashboardStats,
  GraphData,
  PaginatedResponse,
  Indicator,
  IndicatorHistory,
  Insight,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://192.168.50.114";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error ${res.status}: ${error}`);
  }

  return res.json();
}

// Dashboard
export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>("/api/dashboard/stats");
}

// Predictions
export async function getPredictions(params?: {
  page?: number;
  page_size?: number;
  time_horizon?: string;
  status?: string;
  category?: string;
}): Promise<PaginatedResponse<Prediction>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size)
    searchParams.set("page_size", String(params.page_size));
  if (params?.time_horizon)
    searchParams.set("time_horizon", params.time_horizon);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.category) searchParams.set("category", params.category);

  const query = searchParams.toString();
  return fetchApi<PaginatedResponse<Prediction>>(
    `/api/predictions${query ? `?${query}` : ""}`
  );
}

export async function getPrediction(id: string): Promise<Prediction> {
  return fetchApi<Prediction>(`/api/predictions/${id}`);
}

// Agents
export async function getAgents(): Promise<Agent[]> {
  return fetchApi<Agent[]>("/api/agents");
}

export async function getAgent(id: string): Promise<Agent> {
  return fetchApi<Agent>(`/api/agents/${id}`);
}

// Interests
export async function getInterests(): Promise<UserInterest[]> {
  return fetchApi<UserInterest[]>("/api/interests");
}

export async function createInterest(
  interest: Omit<UserInterest, "id" | "created_at" | "updated_at">
): Promise<UserInterest> {
  return fetchApi<UserInterest>("/api/interests", {
    method: "POST",
    body: JSON.stringify(interest),
  });
}

export async function updateInterest(
  id: string,
  interest: Partial<UserInterest>
): Promise<UserInterest> {
  return fetchApi<UserInterest>(`/api/interests/${id}`, {
    method: "PUT",
    body: JSON.stringify(interest),
  });
}

export async function deleteInterest(id: string): Promise<void> {
  return fetchApi<void>(`/api/interests/${id}`, {
    method: "DELETE",
  });
}

// Graph
export async function getGraphData(): Promise<GraphData> {
  return fetchApi<GraphData>("/api/graph");
}

// Webhooks
export async function triggerWebhook(payload: {
  event: string;
  data: Record<string, unknown>;
}): Promise<{ status: string }> {
  return fetchApi<{ status: string }>("/api/webhooks/trigger", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Indicators
export async function getIndicators(params?: {
  agency?: string;
  region?: string;
  series_id?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.agency) searchParams.set("agency", params.agency);
  if (params?.region) searchParams.set("region", params.region);
  if (params?.series_id) searchParams.set("series_id", params.series_id);
  const qs = searchParams.toString();
  return fetchApi<Indicator[]>(`/api/indicators/${qs ? `?${qs}` : ""}`);
}

export async function getIndicatorHistory(seriesId: string, agency?: string) {
  const qs = agency ? `?agency=${agency}` : "";
  return fetchApi<IndicatorHistory>(`/api/indicators/history/${seriesId}${qs}`);
}

// Insights
export async function getInsights(domain?: string) {
  const qs = domain ? `?domain=${domain}` : "";
  return fetchApi<Insight[]>(`/api/insights/${qs}`);
}

export async function getInsight(id: string) {
  return fetchApi<Insight>(`/api/insights/${id}`);
}
