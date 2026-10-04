import api from './client';

/** Tag usage count */
export interface TagTrend {
  name: string;
  color: string;
  count: number;
}

/** Single usage item (deck or spread) */
export interface UsageItem {
  name: string;
  count: number;
}

/** Deck and spread usage stats */
export interface UsageStats {
  top_decks: UsageItem[];
  top_spreads: UsageItem[];
}

export async function getTagTrends(limit?: number): Promise<TagTrend[]> {
  const query = limit ? `?limit=${limit}` : '';
  const res = await api.get(`/api/stats/tag-trends${query}`);
  return res.data;
}

export async function getUsageStats(limit?: number): Promise<UsageStats> {
  const query = limit ? `?limit=${limit}` : '';
  const res = await api.get(`/api/stats/usage${query}`);
  return res.data;
}

/** Correspondence field value frequency */
export interface CorrespondenceFrequency {
  value: string;
  count: number;
}

export async function getCorrespondenceFrequency(
  field: string,
  months?: number,
): Promise<CorrespondenceFrequency[]> {
  const params = new URLSearchParams({ field });
  if (months) params.set('months', String(months));
  const res = await api.get(`/api/stats/correspondence-frequency?${params}`);
  return res.data;
}
