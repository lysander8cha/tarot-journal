import api from './client';
import type { Profile } from '../types';

export async function getProfiles(): Promise<Profile[]> {
  const res = await api.get('/api/profiles');
  return res.data;
}

export async function getProfile(profileId: number): Promise<Profile> {
  const res = await api.get(`/api/profiles/${profileId}`);
  return res.data;
}

export async function createProfile(data: {
  name: string;
  gender?: string | null;
  birth_date?: string | null;
  birth_time?: string | null;
  birth_place_name?: string | null;
  birth_place_lat?: number | null;
  birth_place_lon?: number | null;
  querent_only?: boolean;
}): Promise<{ id: number }> {
  const res = await api.post('/api/profiles', data);
  return res.data;
}

export async function updateProfile(profileId: number, data: {
  name?: string;
  gender?: string | null;
  birth_date?: string | null;
  birth_time?: string | null;
  birth_place_name?: string | null;
  birth_place_lat?: number | null;
  birth_place_lon?: number | null;
  querent_only?: boolean;
}): Promise<void> {
  await api.put(`/api/profiles/${profileId}`, data);
}

export async function deleteProfile(profileId: number): Promise<void> {
  await api.delete(`/api/profiles/${profileId}`);
}
