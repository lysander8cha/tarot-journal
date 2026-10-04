import api from './client';

export interface ChartResponse {
  chart_svg: string;
  /** Full kerykeion subject.model_dump() output. Shape isn't strict. */
  chart_data: Record<string, unknown>;
  house_system: string;
  solar_chart?: boolean;
  timezone?: string;
  generated_at?: string;
  cached?: boolean;
}

/** Fetch (or lazy-generate) the natal chart for a profile. */
export async function getProfileChart(profileId: number): Promise<ChartResponse> {
  const res = await api.get(`/api/profiles/${profileId}/chart`);
  return res.data;
}

/** Force-clear the cached chart for a profile. */
export async function deleteProfileChart(profileId: number): Promise<void> {
  await api.delete(`/api/profiles/${profileId}/chart`);
}

/** Fetch (or lazy-generate) the event chart for a journal entry. */
export async function getEntryChart(entryId: number): Promise<ChartResponse> {
  const res = await api.get(`/api/entries/${entryId}/chart`);
  return res.data;
}

/** Force-clear the cached chart for an entry. */
export async function deleteEntryChart(entryId: number): Promise<void> {
  await api.delete(`/api/entries/${entryId}/chart`);
}
