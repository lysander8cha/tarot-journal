import api from './client';

/** When the last phone-logged entry arrived (null = never). */
export async function getPushActivity(): Promise<{ last_push_at: string | null }> {
  const res = await api.get('/api/sync/push-activity');
  return res.data;
}
