import api from './client';
import type { CorrespondenceSystem, CorrespondenceAssignment, ResolvedCorrespondence } from '../types';

// === Correspondence Systems ===

export async function getCorrespondenceSystems(): Promise<CorrespondenceSystem[]> {
  const res = await api.get('/api/correspondence-systems');
  return res.data;
}

export async function getCorrespondenceSystem(systemId: number): Promise<CorrespondenceSystem & { assignments: CorrespondenceAssignment[] }> {
  const res = await api.get(`/api/correspondence-systems/${systemId}`);
  return res.data;
}

export async function createCorrespondenceSystem(data: {
  name: string;
  description?: string;
  cartomancy_type?: string;
  naming_style?: string;
}): Promise<{ id: number }> {
  const res = await api.post('/api/correspondence-systems', data);
  return res.data;
}

export async function updateCorrespondenceSystem(systemId: number, data: { name?: string; description?: string }) {
  await api.put(`/api/correspondence-systems/${systemId}`, data);
}

export async function deleteCorrespondenceSystem(systemId: number) {
  await api.delete(`/api/correspondence-systems/${systemId}`);
}

export async function cloneCorrespondenceSystem(systemId: number, name: string): Promise<{ id: number }> {
  const res = await api.post(`/api/correspondence-systems/${systemId}/clone`, { name });
  return res.data;
}

// === System Assignments ===

export async function getSystemAssignments(
  systemId: number,
  archetypeId?: number,
): Promise<CorrespondenceAssignment[]> {
  const params = archetypeId ? { archetype_id: archetypeId } : {};
  const res = await api.get(`/api/correspondence-systems/${systemId}/assignments`, { params });
  return res.data;
}

export async function setAssignmentValues(
  systemId: number,
  archetypeId: number,
  fieldName: string,
  values: string[],
  sourceGroup?: string,
) {
  await api.put(`/api/correspondence-systems/${systemId}/assignments/${archetypeId}/${fieldName}`, {
    values,
    source_group: sourceGroup ?? null,
  });
}

export async function expandElementalZodiac(
  systemId: number,
  archetypeIds: number[],
  sourceGroup: string,
) {
  const res = await api.post(
    `/api/correspondence-systems/${systemId}/expand-elemental-zodiac`,
    { archetype_ids: archetypeIds, source_group: sourceGroup },
  );
  return res.data;
}

export async function deleteAssignment(
  systemId: number,
  archetypeId: number,
  fieldName: string,
  options?: { sourceGroup?: string; all?: boolean },
) {
  const params = new URLSearchParams();
  if (options?.sourceGroup) params.set('source_group', options.sourceGroup);
  if (options?.all) params.set('all', 'true');
  const qs = params.toString() ? `?${params}` : '';
  await api.delete(`/api/correspondence-systems/${systemId}/assignments/${archetypeId}/${fieldName}${qs}`);
}

// === Card-Level Overrides ===

export async function getCardCorrespondences(cardId: number): Promise<ResolvedCorrespondence[]> {
  const res = await api.get(`/api/cards/${cardId}/correspondences`);
  return res.data;
}

export async function setCardOverrides(
  cardId: number,
  overrides: { field_name: string; field_value?: string | null; field_values?: string[] }[],
) {
  await api.put(`/api/cards/${cardId}/correspondences`, { overrides });
}

// === Deck-Level Overrides ===

export interface DeckCorrespondenceOverride {
  id: number;
  deck_id: number;
  archetype_id: number;
  archetype_name: string;
  cartomancy_type: string;
  rank: string | null;
  suit: string | null;
  card_type: string | null;
  field_name: string;
  field_value: string;
  source_group: string | null;
}

export async function getDeckCorrespondenceOverrides(deckId: number): Promise<DeckCorrespondenceOverride[]> {
  const res = await api.get(`/api/decks/${deckId}/correspondence-overrides`);
  return res.data;
}

export async function setDeckCorrespondenceOverride(
  deckId: number,
  archetypeId: number,
  fieldName: string,
  values: string[],
  sourceGroup?: string,
) {
  await api.put(`/api/decks/${deckId}/correspondence-overrides`, {
    archetype_id: archetypeId,
    field_name: fieldName,
    values,
    source_group: sourceGroup ?? null,
  });
}

export async function deleteDeckCorrespondenceGroup(
  deckId: number,
  sourceGroup: string,
  fieldName?: string,
) {
  const params = new URLSearchParams({ source_group: sourceGroup });
  if (fieldName) params.set('field_name', fieldName);
  await api.delete(`/api/decks/${deckId}/correspondence-overrides/group?${params}`);
}

// === Cross-System Queries ===

export async function compareCorrespondenceSystems(systemIds: number[]): Promise<CorrespondenceAssignment[]> {
  const res = await api.get('/api/correspondences/compare', {
    params: { systems: systemIds.join(',') },
  });
  return res.data;
}

// === Archetypes (for bulk editing) ===

export interface Archetype {
  id: number;
  name: string;
  cartomancy_type: string;
  rank: string | null;
  suit: string | null;
  card_type: string | null;
}

export async function getArchetypes(cartomancyType?: string): Promise<Archetype[]> {
  const params = cartomancyType ? { cartomancy_type: cartomancyType } : {};
  const res = await api.get('/api/archetypes', { params });
  return res.data;
}

// === Field Options ===

export interface FieldOption {
  id: number;
  field_name: string;
  option_value: string;
  sort_order: number;
}

export async function getFieldOptions(fieldName?: string): Promise<FieldOption[]> {
  const params = fieldName ? { field: fieldName } : {};
  const res = await api.get('/api/correspondence-field-options', { params });
  return res.data;
}

export async function addFieldOption(fieldName: string, optionValue: string): Promise<{ id: number }> {
  const res = await api.post('/api/correspondence-field-options', {
    field_name: fieldName,
    option_value: optionValue,
  });
  return res.data;
}

export async function updateFieldOption(optionId: number, data: { option_value?: string; sort_order?: number }) {
  await api.put(`/api/correspondence-field-options/${optionId}`, data);
}

export async function deleteFieldOption(optionId: number) {
  await api.delete(`/api/correspondence-field-options/${optionId}`);
}

export async function reorderFieldOptions(fieldName: string, orderedIds: number[]) {
  await api.post('/api/correspondence-field-options/reorder', {
    field_name: fieldName,
    ordered_ids: orderedIds,
  });
}
