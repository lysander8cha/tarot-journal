import api from './client';
import type { Deck, CartomancyType, DeckCustomField } from '../types';

export async function getDecks(typeId?: number): Promise<Deck[]> {
  const params = typeId ? { type_id: typeId } : {};
  const res = await api.get('/api/decks', { params });
  return res.data;
}

export async function getDeck(deckId: number): Promise<Deck> {
  const res = await api.get(`/api/decks/${deckId}`);
  return res.data;
}

export async function getCartomancyTypes(): Promise<CartomancyType[]> {
  const res = await api.get('/api/types');
  return res.data;
}

export async function getDeckGroups(deckId: number): Promise<import('../types').CardGroup[]> {
  const res = await api.get(`/api/decks/${deckId}/groups`);
  return res.data;
}

export async function updateDeck(
  deckId: number,
  data: Partial<Pick<Deck, 'name' | 'date_published' | 'publisher' | 'credits' | 'notes' | 'booklet_info' | 'cartomancy_type_id'>>
    & { suit_names?: Record<string, string> | null; court_names?: Record<string, string> | null },
) {
  await api.put(`/api/decks/${deckId}`, data);
}

export async function getDeckTagAssignments(deckId: number): Promise<import('../types').Tag[]> {
  const res = await api.get(`/api/decks/${deckId}/tags`);
  return res.data;
}

export async function setDeckTags(deckId: number, tagIds: number[]) {
  await api.put(`/api/decks/${deckId}/tags`, { tag_ids: tagIds });
}

// ── Deck Custom Fields ──

export async function getDeckCustomFields(deckId: number): Promise<DeckCustomField[]> {
  const res = await api.get(`/api/decks/${deckId}/custom-fields`);
  return res.data;
}

export async function addDeckCustomField(
  deckId: number,
  data: { field_name: string; field_type?: string; field_options?: string[]; field_order?: number },
): Promise<{ id: number }> {
  const res = await api.post(`/api/decks/${deckId}/custom-fields`, data);
  return res.data;
}

export async function updateDeckCustomField(
  fieldId: number,
  data: { field_name?: string; field_type?: string; field_options?: string[]; field_order?: number },
) {
  await api.put(`/api/decks/custom-fields/${fieldId}`, data);
}

export async function deleteDeckCustomField(fieldId: number) {
  await api.delete(`/api/decks/custom-fields/${fieldId}`);
}

// ── Suit/Court Name Updates (with card renaming) ──

export async function updateDeckSuitNames(
  deckId: number,
  suitNames: Record<string, string>,
  oldSuitNames?: Record<string, string>,
) {
  await api.put(`/api/decks/${deckId}/suit-names`, {
    suit_names: suitNames,
    old_suit_names: oldSuitNames,
  });
}

export async function updateDeckCourtNames(
  deckId: number,
  courtNames: Record<string, string>,
  oldCourtNames?: Record<string, string>,
) {
  await api.put(`/api/decks/${deckId}/court-names`, {
    court_names: courtNames,
    old_court_names: oldCourtNames,
  });
}

// ── Deck Type Assignments (multi-type support) ──

export async function getDeckTypes(deckId: number): Promise<{ id: number; name: string }[]> {
  const res = await api.get(`/api/decks/${deckId}/types`);
  return res.data;
}

export async function setDeckTypes(deckId: number, typeIds: number[]) {
  await api.put(`/api/decks/${deckId}/types`, { type_ids: typeIds });
}
