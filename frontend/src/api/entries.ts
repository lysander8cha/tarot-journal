import api, { API_BASE } from './client';
import type {
  JournalEntry, JournalEntryFull, EntryReadingParsed,
  FollowUpNote, Tag, Profile,
} from '../types';

// ── Entries ──────────────────────────────────────────────────

export type EntrySort = 'reading' | 'created';

export async function getEntries(
  limit = 50,
  offset = 0,
  sort: EntrySort = 'reading',
): Promise<JournalEntry[]> {
  const res = await api.get('/api/entries', { params: { limit, offset, sort } });
  return res.data;
}

export async function getEntry(entryId: number): Promise<JournalEntryFull> {
  const res = await api.get(`/api/entries/${entryId}`);
  return res.data;
}

export interface RecentLocation {
  location_name: string;
  location_lat: number | null;
  location_lon: number | null;
}

export async function getRecentLocations(): Promise<RecentLocation[]> {
  const res = await api.get('/api/entries/recent-locations');
  return res.data;
}

export async function searchEntries(params: {
  query?: string;
  tag_ids?: number[];
  deck_id?: number;
  spread_id?: number;
  cartomancy_type?: string;
  card_name?: string;
  date_from?: string;
  date_to?: string;
  querent_id?: number;
  sort?: EntrySort;
}): Promise<JournalEntry[]> {
  const p: Record<string, string> = {};
  if (params.sort) p.sort = params.sort;
  if (params.query) p.query = params.query;
  if (params.tag_ids?.length) p.tag_ids = params.tag_ids.join(',');
  if (params.deck_id) p.deck_id = String(params.deck_id);
  if (params.spread_id) p.spread_id = String(params.spread_id);
  if (params.cartomancy_type) p.cartomancy_type = params.cartomancy_type;
  if (params.card_name) p.card_name = params.card_name;
  if (params.date_from) p.date_from = params.date_from;
  if (params.date_to) p.date_to = params.date_to;
  if (params.querent_id) p.querent_id = String(params.querent_id);
  const res = await api.get('/api/entries/search', { params: p });
  return res.data;
}

export async function createEntry(data: {
  title?: string;
  content?: string;
  reading_datetime?: string;
  location_name?: string;
  location_lat?: number | null;
  location_lon?: number | null;
  querent_id?: number | null;
  reader_id?: number | null;
}): Promise<{ id: number }> {
  const res = await api.post('/api/entries', data);
  return res.data;
}

export async function updateEntry(entryId: number, data: {
  title?: string;
  content?: string;
  reading_datetime?: string;
  location_name?: string;
  location_lat?: number | null;
  location_lon?: number | null;
  querent_id?: number | null;
  reader_id?: number | null;
}): Promise<void> {
  await api.put(`/api/entries/${entryId}`, data);
}

export async function deleteEntry(entryId: number): Promise<void> {
  await api.delete(`/api/entries/${entryId}`);
}

/** Persist Reading Breakdown panel state for an entry. */
export async function setEntryBreakdownSettings(
  entryId: number,
  settings: Record<string, unknown>,
): Promise<void> {
  await api.patch(`/api/entries/${entryId}/breakdown-settings`, settings);
}

// ── Readings ─────────────────────────────────────────────────

export async function getEntryReadings(entryId: number): Promise<EntryReadingParsed[]> {
  const res = await api.get(`/api/entries/${entryId}/readings`);
  return res.data;
}

export async function addEntryReading(entryId: number, data: {
  spread_id?: number | null;
  spread_name?: string;
  deck_id?: number | null;
  deck_name?: string;
  cartomancy_type?: string;
  cards_used?: Array<{ name: string; reversed?: boolean; deck_id?: number; deck_name?: string; position_index?: number; card_id?: number; clarifies?: number }>;
  position_order?: number;
}): Promise<{ id: number }> {
  const res = await api.post(`/api/entries/${entryId}/readings`, data);
  return res.data;
}

export async function deleteEntryReadings(entryId: number): Promise<void> {
  await api.delete(`/api/entries/${entryId}/readings`);
}

/** Atomically replace all of an entry's readings in a single request.
 *  The backend performs the swap in one database transaction, so a
 *  failure can never leave the entry with its readings half-deleted.
 *  Always prefer this over deleteEntryReadings + addEntryReading loops. */
export async function replaceEntryReadings(entryId: number, readings: Array<{
  notes?: string;
  spread_id?: number | null;
  spread_name?: string;
  deck_id?: number | null;
  deck_name?: string;
  cartomancy_type?: string;
  cards_used?: Array<{ name: string; reversed?: boolean; deck_id?: number; deck_name?: string; position_index?: number; card_id?: number; clarifies?: number }>;
  position_order?: number;
}>): Promise<{ ids: number[] }> {
  const res = await api.put(`/api/entries/${entryId}/readings`, { readings });
  return res.data;
}

/** The entry rendered as LLM-ready markdown (the "Librarian" export)
 *  for pasting into any AI chat. */
export async function getEntryLlmMarkdown(
  entryId: number,
  /** Append the drawn cards' reference material (deck custom fields,
   *  archetype source notes) — used by the Mirror for factual lookups. */
  includeReference = false,
): Promise<string> {
  const res = await api.get(`/api/entries/${entryId}/llm-export`, {
    params: includeReference ? { include_reference: '1' } : {},
  });
  return res.data.markdown;
}

/** Several entries bundled into one LLM-ready document, chronological,
 *  prefixed with app-computed statistics (the Analyst's source). */
export async function getBulkLlmMarkdown(entryIds: number[]): Promise<{
  markdown: string;
  entry_count: number;
  char_count: number;
}> {
  const res = await api.post('/api/entries/llm-export', { ids: entryIds });
  return res.data;
}

// ── Follow-up Notes ──────────────────────────────────────────

export async function getFollowUpNotes(entryId: number): Promise<FollowUpNote[]> {
  const res = await api.get(`/api/entries/${entryId}/follow-up-notes`);
  return res.data;
}

export async function addFollowUpNote(entryId: number, content: string): Promise<{ id: number }> {
  const res = await api.post(`/api/entries/${entryId}/follow-up-notes`, { content });
  return res.data;
}

export async function updateFollowUpNote(noteId: number, content: string): Promise<void> {
  await api.put(`/api/follow-up-notes/${noteId}`, { content });
}

export async function deleteFollowUpNote(noteId: number): Promise<void> {
  await api.delete(`/api/follow-up-notes/${noteId}`);
}

// ── Entry Tags ───────────────────────────────────────────────

export async function getEntryTags(entryId: number): Promise<Tag[]> {
  const res = await api.get(`/api/entries/${entryId}/tags`);
  return res.data;
}

export async function setEntryTags(entryId: number, tagIds: number[]): Promise<void> {
  await api.put(`/api/entries/${entryId}/tags`, { tag_ids: tagIds });
}

// ── Entry Querents ──────────────────────────────────────────

export async function setEntryQuerents(entryId: number, profileIds: number[]): Promise<void> {
  await api.put(`/api/entries/${entryId}/querents`, { profile_ids: profileIds });
}

// ── Profiles ─────────────────────────────────────────────────

export async function getProfiles(): Promise<Profile[]> {
  const res = await api.get('/api/profiles');
  return res.data;
}

// ── Export / Import ──────────────────────────────────────────

export function exportEntriesUrl(entryIds?: number[]): string {
  const params = entryIds?.length ? `?ids=${entryIds.join(',')}` : '';
  return `${API_BASE}/api/entries/export${params}`;
}

export async function importEntries(data: unknown, mergeTags = true): Promise<{
  imported: number;
  skipped: number;
  tags_created: number;
}> {
  const res = await api.post('/api/entries/import', { data, merge_tags: mergeTags });
  return res.data;
}
