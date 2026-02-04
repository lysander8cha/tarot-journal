import api from './client';

/** Basic app stats (totals and top 5 lists) */
export interface AppStats {
  total_entries: number;
  total_decks: number;
  total_cards: number;
  total_spreads: number;
  top_decks: Array<[string, number]>;
  top_spreads: Array<[string, number]>;
}

/** Extended stats with additional metrics for the Stats tab */
export interface ExtendedStats extends AppStats {
  entries_this_month: number;
  total_readings: number;
  unique_cards_drawn: number;
  avg_cards_per_reading: number;
}

/** Card frequency data for visualization */
export interface CardFrequency {
  name: string;
  count: number;
  reversed_count: number;
}

/** Timeline data point (one per month) */
export interface TimelinePeriod {
  period: string;
  entries: number;
  readings: number;
}

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

export async function getStats(): Promise<AppStats> {
  const res = await api.get('/api/stats');
  return res.data;
}

export async function getExtendedStats(): Promise<ExtendedStats> {
  const res = await api.get('/api/stats/extended');
  return res.data;
}

export async function getCardFrequency(
  limit?: number,
  deckId?: number
): Promise<CardFrequency[]> {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (deckId) params.set('deck_id', String(deckId));

  const query = params.toString();
  const res = await api.get(`/api/stats/card-frequency${query ? `?${query}` : ''}`);
  return res.data;
}

export async function getTimeline(limit?: number): Promise<TimelinePeriod[]> {
  const query = limit ? `?limit=${limit}` : '';
  const res = await api.get(`/api/stats/timeline${query}`);
  return res.data;
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
