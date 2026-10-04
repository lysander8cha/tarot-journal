import { API_BASE } from './client';

/** URL for a card's thumbnail image (300x450) */
export function cardThumbnailUrl(cardId: number): string {
  return `${API_BASE}/api/images/card/${cardId}/thumbnail`;
}

/** URL for a card's preview image (500x750) */
export function cardPreviewUrl(cardId: number): string {
  return `${API_BASE}/api/images/card/${cardId}/preview`;
}

/** URL for a deck's card-back image */
export function deckBackUrl(deckId: number): string {
  return `${API_BASE}/api/images/deck/${deckId}/back`;
}
