import api from './client';
import type { Spread, SpreadPosition, DeckSlot } from '../types';

export async function getSpreads(): Promise<Spread[]> {
  const res = await api.get('/api/spreads');
  return res.data;
}

export async function getSpread(spreadId: number): Promise<Spread> {
  const res = await api.get(`/api/spreads/${spreadId}`);
  return res.data;
}

export async function createSpread(data: {
  name: string;
  positions?: SpreadPosition[];
  description?: string;
  cartomancy_type?: string;
  allowed_deck_types?: string[];
  default_deck_id?: number | null;
  deck_slots?: DeckSlot[];
  source_id?: number | null;
}): Promise<{ id: number }> {
  const res = await api.post('/api/spreads', data);
  return res.data;
}

export async function updateSpread(spreadId: number, data: {
  name?: string;
  positions?: SpreadPosition[];
  description?: string;
  allowed_deck_types?: string[] | null;
  default_deck_id?: number | null;
  clear_default_deck?: boolean;
  deck_slots?: DeckSlot[] | null;
  archived?: boolean;
  /** Present-but-null clears the attribution. */
  source_id?: number | null;
}): Promise<void> {
  await api.put(`/api/spreads/${spreadId}`, data);
}

export async function deleteSpread(spreadId: number): Promise<void> {
  await api.delete(`/api/spreads/${spreadId}`);
}

export async function setSpreadTags(spreadId: number, tagIds: number[]) {
  await api.put(`/api/spreads/${spreadId}/tags`, { tag_ids: tagIds });
}

export async function cloneSpread(spreadId: number, name?: string): Promise<{ id: number }> {
  const res = await api.post(`/api/spreads/${spreadId}/clone`, name ? { name } : {});
  return res.data;
}
