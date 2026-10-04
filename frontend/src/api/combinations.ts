import api from './client';
import type { CombinationMeaning } from '../types';

// Sources are managed via the shared `referenceSources` API — see
// frontend/src/api/referenceSources.ts.

// === Meanings ===

export async function getCombinationMeanings(
  cartomancyType: string,
  card1: number,
  card2: number,
  card1Reversed = false,
  card2Reversed = false,
  card3: number | null = null,
  card3Reversed = false,
): Promise<CombinationMeaning[]> {
  const res = await api.get('/api/combinations/meanings', {
    params: {
      cartomancy_type: cartomancyType,
      card_1: card1,
      card_2: card2,
      ...(card1Reversed ? { card_1_reversed: '1' } : {}),
      ...(card2Reversed ? { card_2_reversed: '1' } : {}),
      ...(card3 ? { card_3: card3 } : {}),
      ...(card3 && card3Reversed ? { card_3_reversed: '1' } : {}),
    },
  });
  return res.data;
}

/** Cartomancy types whose combinations may involve reversed cards. */
export async function getReversedCombinationTypes(): Promise<string[]> {
  const res = await api.get('/api/combinations/reversed-types');
  return res.data.types;
}

export async function setReversedCombinationTypes(types: string[]): Promise<void> {
  await api.put('/api/combinations/reversed-types', { types });
}

export async function createCombinationMeaning(
  cartomancyType: string,
  card1: number,
  card2: number,
  meaning: string,
  sourceId: number | null = null,
  card1Reversed = false,
  card2Reversed = false,
  card3: number | null = null,
  card3Reversed = false,
): Promise<{ id: number }> {
  const res = await api.post('/api/combinations/meanings', {
    cartomancy_type: cartomancyType,
    card_1: card1,
    card_2: card2,
    meaning,
    source_id: sourceId,
    card_1_reversed: card1Reversed,
    card_2_reversed: card2Reversed,
    card_3: card3,
    card_3_reversed: card3Reversed,
  });
  return res.data;
}

export async function updateCombinationMeaning(
  meaningId: number,
  patch: { meaning?: string; source_id?: number | null },
) {
  await api.put(`/api/combinations/meanings/${meaningId}`, patch);
}

export async function deleteCombinationMeaning(meaningId: number) {
  await api.delete(`/api/combinations/meanings/${meaningId}`);
}

export async function reorderCombinationMeanings(
  combinationId: number,
  orderedIds: number[],
) {
  await api.post('/api/combinations/meanings/reorder', {
    combination_id: combinationId,
    ordered_ids: orderedIds,
  });
}

/** Partner archetypes that already have authored meanings, keyed by
 *  archetype id (string) → meaning count. Drives the "n meanings"
 *  hints in the combination pickers. */
/** Meanings the same pair/triad holds under OTHER reversal states. */
export async function getOtherReversalCount(
  cartomancyType: string,
  card1: number,
  card2: number,
  card1Reversed = false,
  card2Reversed = false,
  card3: number | null = null,
  card3Reversed = false,
): Promise<number> {
  const res = await api.get('/api/combinations/meanings/other-reversals', {
    params: {
      cartomancy_type: cartomancyType,
      card_1: card1,
      card_2: card2,
      ...(card1Reversed ? { card_1_reversed: '1' } : {}),
      ...(card2Reversed ? { card_2_reversed: '1' } : {}),
      ...(card3 != null ? { card_3: card3 } : {}),
      ...(card3Reversed ? { card_3_reversed: '1' } : {}),
    },
  });
  return res.data.count;
}

export async function getCombinationPartners(params: {
  cartomancyType: string;
  card1: number;
  card1Reversed?: boolean;
  triad?: boolean;
  card2?: number | null;
  card2Reversed?: boolean;
}): Promise<Record<string, number>> {
  const res = await api.get('/api/combinations/partners', {
    params: {
      cartomancy_type: params.cartomancyType,
      card_1: params.card1,
      ...(params.card1Reversed ? { card_1_reversed: '1' } : {}),
      ...(params.triad ? { triad: '1' } : {}),
      ...(params.card2 != null ? { card_2: params.card2 } : {}),
      ...(params.card2Reversed ? { card_2_reversed: '1' } : {}),
    },
  });
  return res.data.partners;
}

/** All of a type's meanings from one source (null = unattributed),
 *  with combination and archetype info, ordered by card names. */
export async function getCombinationsBySource(
  cartomancyType: string,
  sourceId: number | null,
): Promise<CombinationMeaning[]> {
  const res = await api.get('/api/combinations/by-source', {
    params: {
      cartomancy_type: cartomancyType,
      source_id: sourceId == null ? 'none' : sourceId,
    },
  });
  return res.data;
}
