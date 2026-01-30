import api from './client';
import type { Card } from '../types';

export async function getCards(deckId: number): Promise<Card[]> {
  const res = await api.get('/api/cards', { params: { deck_id: deckId } });
  return res.data;
}

export async function getCard(cardId: number): Promise<Card> {
  const res = await api.get(`/api/cards/${cardId}`);
  return res.data;
}

export async function searchCards(params: Record<string, string | number | boolean>): Promise<Card[]> {
  const res = await api.get('/api/cards/search', { params });
  return res.data;
}

export async function updateCard(cardId: number, data: Partial<Pick<Card, 'name' | 'card_order'>>) {
  await api.put(`/api/cards/${cardId}`, data);
}

export async function updateCardMetadata(
  cardId: number,
  data: { archetype?: string; rank?: string; suit?: string; notes?: string; custom_fields?: string },
) {
  await api.put(`/api/cards/${cardId}/metadata`, data);
}

export async function setCardTags(cardId: number, tagIds: number[]) {
  await api.put(`/api/cards/${cardId}/tags`, { tag_ids: tagIds });
}

export async function setCardGroups(cardId: number, groupIds: number[]) {
  await api.put(`/api/cards/${cardId}/groups`, { group_ids: groupIds });
}

export interface CardCustomField {
  id: number;
  card_id: number;
  field_name: string;
  field_type: string;
  field_value: string | null;
  field_options: string | null;
  field_order: number;
}

export async function getCardCustomFields(cardId: number): Promise<CardCustomField[]> {
  const res = await api.get(`/api/cards/${cardId}/custom-fields`);
  return res.data;
}

export async function addCardCustomField(
  cardId: number,
  data: { field_name: string; field_type?: string; field_value?: string; field_options?: string[]; field_order?: number },
): Promise<{ id: number }> {
  const res = await api.post(`/api/cards/${cardId}/custom-fields`, data);
  return res.data;
}

export async function updateCardCustomField(
  fieldId: number,
  data: { field_name?: string; field_value?: string },
) {
  await api.put(`/api/cards/custom-fields/${fieldId}`, data);
}

export async function deleteCardCustomField(fieldId: number) {
  await api.delete(`/api/cards/custom-fields/${fieldId}`);
}
