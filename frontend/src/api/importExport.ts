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

export interface ImportPresetDetail {
  name: string;
  type: string;
  description: string;
  suit_names: Record<string, string>;
  card_count: number;
  is_builtin: boolean;
  is_customized: boolean;
  /** Card name → list of filename patterns that trigger it */
  mappings_grouped: Record<string, string[]>;
}

export async function getImportPresetsDetails(): Promise<ImportPresetDetail[]> {
  const res = await api.get('/api/import/presets/details');
  return res.data;
}

export async function saveImportPreset(data: {
  name: string;
  type: string;
  description: string;
  suit_names: Record<string, string>;
  mappings?: Record<string, string>;
}): Promise<void> {
  await api.post('/api/import/presets', data);
}

export async function deleteImportPreset(name: string): Promise<void> {
  await api.delete(`/api/import/presets/${encodeURIComponent(name)}`);
}

export async function resetImportPreset(name: string): Promise<void> {
  await api.post(`/api/import/presets/${encodeURIComponent(name)}/reset`);
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

export async function scanNewCards(deckId: number, folder: string): Promise<{
  cards: { filename: string; name: string }[];
  count: number;
  existing_count: number;
}> {
  const res = await api.post('/api/import/scan-new-cards', { deck_id: deckId, folder });
  return res.data;
}

export async function addCardsToDeck(deckId: number, folder: string): Promise<{
  cards_added: number;
  filenames: string[];
}> {
  const res = await api.post('/api/import/add-cards-to-deck', { deck_id: deckId, folder });
  return res.data;
}

export function exportDeckUrl(deckId: number): string {
  return `${API_BASE}/api/export/deck/${deckId}`;
}
