import api from './client';
import type { Theme } from '../types';

// === Theme ===

export async function getTheme(): Promise<Theme> {
  const res = await api.get('/api/theme');
  return res.data;
}

export async function updateTheme(theme: Partial<Theme>): Promise<Theme> {
  const res = await api.put('/api/theme', theme);
  return res.data;
}

export async function getThemePresets(): Promise<Record<string, Theme>> {
  const res = await api.get('/api/theme/presets');
  return res.data;
}

export async function applyThemePreset(presetName: string): Promise<Theme> {
  const res = await api.post('/api/theme/apply-preset', { preset_name: presetName });
  return res.data;
}

// === Defaults ===

export interface AppDefaults {
  default_querent: number | null;
  default_reader: number | null;
  default_querent_same_as_reader: boolean;
  default_decks: Record<string, number | null>;
  last_backup_time: string | null;
}

export async function getDefaults(): Promise<AppDefaults> {
  const res = await api.get('/api/settings/defaults');
  return res.data;
}

export async function updateDefaults(data: Partial<AppDefaults>): Promise<void> {
  await api.put('/api/settings/defaults', data);
}

// === Backup & Restore ===

export async function createBackup(includeImages: boolean): Promise<Blob> {
  const res = await api.post('/api/backup', { include_images: includeImages }, {
    responseType: 'blob',
  });
  return res.data;
}

export async function restoreBackup(file: File): Promise<{ entries_restored?: number; decks_restored?: number }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/api/backup/restore', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

// === Cache ===

export interface CacheStats {
  count: number;
  size_bytes: number;
}

export async function getCacheStats(): Promise<CacheStats> {
  const res = await api.get('/api/cache/stats');
  return res.data;
}

export async function clearCache(): Promise<void> {
  await api.post('/api/cache/clear');
}
