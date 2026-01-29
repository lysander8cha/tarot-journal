import api from './client';
import { API_BASE } from './client';

// Types for import customization
export interface ScanFolderParams {
  folder: string;
  preset_name: string;
  custom_suit_names?: Record<string, string>;
  custom_court_names?: Record<string, string>;
  archetype_mapping?: string;
}

export interface ImportFromFolderParams {
  folder: string;
  deck_name: string;
  cartomancy_type_id: number;
  preset_name: string;
  custom_suit_names?: Record<string, string>;
  custom_court_names?: Record<string, string>;
  archetype_mapping?: string;
}

export interface PreviewCard {
  filename: string;
  name: string;
  sort_order: number;
  archetype?: string;
  rank?: string;
  suit?: string;
}

export async function getImportPresets(): Promise<string[]> {
  const res = await api.get('/api/import/presets');
  return res.data;
}

export async function getPresetInfo(presetName: string): Promise<{
  type: string;
  suit_names?: Record<string, string>;
} | null> {
  const res = await api.get('/api/import/preset-info', { params: { preset_name: presetName } });
  return res.data;
}

export async function scanFolder(params: ScanFolderParams): Promise<{
  cards: PreviewCard[];
  card_back: string | null;
  count: number;
}> {
  const res = await api.post('/api/import/scan-folder', params);
  return res.data;
}

export async function importFromFolder(data: ImportFromFolderParams): Promise<{
  deck_id: number;
  cards_imported: number;
}> {
  const res = await api.post('/api/import/from-folder', data);
  return res.data;
}

export function exportDeckUrl(deckId: number): string {
  return `${API_BASE}/api/export/deck/${deckId}`;
}

export async function importDeckJson(data: unknown): Promise<{
  deck_id: number;
  deck_name: string;
  cards_imported: number;
}> {
  const res = await api.post('/api/import/deck-json', data);
  return res.data;
}
