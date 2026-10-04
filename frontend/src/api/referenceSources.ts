import api from './client';
import type {
  ReferenceSource,
  ArchetypeSourceEntry,
  SourceAuthoringEntry,
  SourceField,
} from '../types';

/** List sources, optionally scoped to a cartomancy type. */
export async function getReferenceSources(cartomancyType?: string): Promise<ReferenceSource[]> {
  const params = cartomancyType ? { cartomancy_type: cartomancyType } : {};
  const res = await api.get('/api/reference/sources', { params });
  return res.data;
}

export async function createReferenceSource(data: {
  name: string;
  cartomancy_types: string[];
  authors?: string[];
}): Promise<{ id: number }> {
  const res = await api.post('/api/reference/sources', data);
  return res.data;
}

/** Partial update — pass only the keys you want to change.
 *  `cartomancy_types` is a full set-replace. */
export async function updateReferenceSource(
  sourceId: number,
  data: { name?: string; cartomancy_types?: string[]; authors?: string[] },
): Promise<void> {
  await api.put(`/api/reference/sources/${sourceId}`, data);
}

export async function deleteReferenceSource(
  sourceId: number,
  reassignTo?: number,
): Promise<void> {
  const params = new URLSearchParams();
  if (reassignTo != null) params.set('reassign_to', String(reassignTo));
  const qs = params.toString() ? `?${params}` : '';
  await api.delete(`/api/reference/sources/${sourceId}${qs}`);
}

export async function getReferenceSourceDependencies(
  sourceId: number,
): Promise<{
  combination_meanings: number;
  archetype_source_entries: number;
  source_fields: number;
}> {
  const res = await api.get(`/api/reference/sources/${sourceId}/dependencies`);
  return res.data;
}

// === Source fields ===

/** List a source's fields, optionally restricted to one cartomancy
 *  type bucket. The Settings UI fetches the active type only. */
export async function getSourceFields(
  sourceId: number,
  cartomancyType?: string,
): Promise<SourceField[]> {
  const params = cartomancyType ? { cartomancy_type: cartomancyType } : {};
  const res = await api.get(`/api/reference/sources/${sourceId}/fields`, { params });
  return res.data;
}

export async function createSourceField(
  sourceId: number,
  data: { name: string; cartomancy_type: string; collapsible?: boolean },
): Promise<{ id: number }> {
  const res = await api.post(`/api/reference/sources/${sourceId}/fields`, data);
  return res.data;
}

export async function updateSourceField(
  fieldId: number,
  data: { name?: string; sort_order?: number; collapsible?: boolean },
): Promise<void> {
  await api.put(`/api/source-fields/${fieldId}`, data);
}

export async function reorderSourceFields(
  sourceId: number,
  cartomancyType: string,
  fieldIds: number[],
): Promise<void> {
  await api.put(`/api/reference/sources/${sourceId}/fields/reorder`, {
    cartomancy_type: cartomancyType,
    field_ids: fieldIds,
  });
}

export async function deleteSourceField(fieldId: number): Promise<void> {
  await api.delete(`/api/source-fields/${fieldId}`);
}

// === Per-archetype source entries ===

/** All non-empty source entries for a given archetype, optionally
 *  scoped to a cartomancy type. */
export async function getArchetypeSourceEntries(
  archetypeId: number,
  cartomancyType?: string,
): Promise<ArchetypeSourceEntry[]> {
  const params = cartomancyType ? { cartomancy_type: cartomancyType } : {};
  const res = await api.get(`/api/archetypes/${archetypeId}/source-entries`, { params });
  return res.data;
}

/** Every entry under a source, optionally scoped to one cartomancy
 *  type bucket. */
export async function getSourceEntries(
  sourceId: number,
  cartomancyType?: string,
): Promise<SourceAuthoringEntry[]> {
  const params = cartomancyType ? { cartomancy_type: cartomancyType } : {};
  const res = await api.get(`/api/reference/sources/${sourceId}/entries`, { params });
  return res.data;
}

/** Upsert content for a single (archetype, field) cell. Blank/whitespace
 *  deletes the row server-side. */
export async function setArchetypeSourceEntry(
  archetypeId: number,
  fieldId: number,
  content: string,
): Promise<void> {
  await api.put(
    `/api/archetypes/${archetypeId}/source-fields/${fieldId}`,
    { content },
  );
}
