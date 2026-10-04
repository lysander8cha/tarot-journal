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

// === Defaults ===

export interface AppDefaults {
  default_querent: number | null;
  default_reader: number | null;
  default_querent_same_as_reader: boolean;
  default_decks: Record<string, number | null>;
  last_backup_time: string | null;
  astrology_house_system: string;
  astrology_allow_solar_chart: boolean;
}

/** Display names accepted by the astrology backend (mapped to Kerykeion
 *  single-letter codes server-side). Keep this in sync with
 *  astrology.HOUSE_SYSTEM_CODES. */
export const HOUSE_SYSTEMS = [
  'Placidus',
  'Whole Sign',
  'Equal',
  'Koch',
  'Regiomontanus',
  'Campanus',
  'Porphyry',
  'Morinus',
  'Alcabitius',
  'Topocentric',
] as const;

export async function getDefaults(): Promise<AppDefaults> {
  const res = await api.get('/api/settings/defaults');
  return res.data;
}

export async function updateDefaults(data: Partial<AppDefaults>): Promise<void> {
  await api.put('/api/settings/defaults', data);
}

// === Backup & Restore ===

export interface BackupStatus {
  last_auto_snapshot: string | null;
  auto_snapshot_count: number;
  last_backup_time: string | null;
  last_backup_with_images_time: string | null;
}

export async function getBackupStatus(): Promise<BackupStatus> {
  const res = await api.get('/api/backup/status');
  return res.data;
}

/** The backend writes the zip straight to ~/Downloads and returns its
 *  path — the bytes never pass through the app window (a with-images
 *  backup is several GB; buffering it as a Blob crashed the window).
 *  Long timeout: zipping ten thousand images takes a while. */
export async function createBackup(includeImages: boolean): Promise<{ path: string; bytes: number }> {
  const res = await api.post('/api/backup', { include_images: includeImages }, {
    timeout: 1_800_000,
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

// === Indicate Birth & Name Cards colors ===

export async function getIndicationColors(): Promise<{ colors: Record<string, string> }> {
  const res = await api.get('/api/settings/indication-colors');
  return res.data;
}

export async function updateIndicationColors(
  colors: Record<string, string>,
): Promise<void> {
  await api.put('/api/settings/indication-colors', { colors });
}

// === Phone sync ===

export interface PhoneSyncStatus {
  enabled: boolean;
  paired: boolean;
  device_name: string | null;
  pairing_code_active: boolean;
}

export async function getPhoneSyncStatus(): Promise<PhoneSyncStatus> {
  const res = await api.get('/api/sync/status');
  return res.data;
}

export async function setPhoneSyncEnabled(enabled: boolean): Promise<void> {
  await api.put('/api/sync/enabled', { enabled });
}

export async function startPhonePairing(): Promise<{ code: string; expires_in: number }> {
  const res = await api.post('/api/sync/pairing/start');
  return res.data;
}

export async function unpairPhone(): Promise<void> {
  await api.post('/api/sync/unpair');
}
