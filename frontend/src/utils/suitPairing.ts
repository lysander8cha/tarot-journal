/**
 * Suit pairing across cartomantic traditions.
 *
 * The user reads with Latin-suited decks (Cups, Swords, Pentacles,
 * Wands — including Spanish and Italian variants), French-suited
 * ones (Hearts, Spades, Diamonds, Clubs) and German-suited ones
 * (Hearts, Leaves, Bells, Acorns). Suit statistics can render
 * "separate" (each tradition's names as their own rows — the raw
 * data) or "paired" (equivalents merged: "Cups / Hearts").
 *
 * The chosen mode is a single preference shared by every suit display
 * (Insights, the journal's Reading Breakdown) via localStorage.
 */

export type SuitViewMode = 'separate' | 'paired';

export const SUIT_VIEW_STORAGE_KEY = 'tj-suit-view-mode';

const PAIRS: [string, string[]][] = [
  ['Cups / Hearts', ['cups', 'hearts', 'copas', 'coppe', 'herz', 'coupes', 'chalices', 'cœurs', 'coeurs']],
  ['Swords / Spades', ['swords', 'spades', 'espadas', 'spade', 'leaves', 'laub', 'grün', 'gras', 'épées', 'epees', 'piques']],
  ['Pentacles / Diamonds', ['pentacles', 'diamonds', 'oros', 'coins', 'denari', 'bells', 'schellen', 'disks', 'discs', 'deniers', 'carreaux']],
  ['Wands / Clubs', ['wands', 'clubs', 'bastos', 'batons', 'bastoni', 'acorns', 'eichel', 'bâtons', 'staves', 'trèfles', 'trefles']],
];

const LOOKUP = new Map<string, string>();
for (const [label, names] of PAIRS) {
  for (const n of names) LOOKUP.set(n, label);
}

/** The paired label for a suit, or the suit itself when it has no
 *  pair (Major Arcana, oracle groupings…). */
export function pairedSuitLabel(suit: string): string {
  return LOOKUP.get(suit.trim().toLowerCase()) ?? suit;
}

export function loadSuitViewMode(): SuitViewMode {
  try {
    return localStorage.getItem(SUIT_VIEW_STORAGE_KEY) === 'paired' ? 'paired' : 'separate';
  } catch {
    return 'separate';
  }
}

export function saveSuitViewMode(mode: SuitViewMode): void {
  try {
    localStorage.setItem(SUIT_VIEW_STORAGE_KEY, mode);
  } catch {
    /* private-mode etc. — the toggle still works for the session */
  }
}

/** Merge a suit-count list under paired labels (order: by merged count
 *  descending, then name). */
export function pairSuitCounts<T extends { suit: string; count: number }>(
  items: T[],
): { suit: string; count: number }[] {
  const merged = new Map<string, number>();
  for (const it of items) {
    const label = pairedSuitLabel(it.suit);
    merged.set(label, (merged.get(label) || 0) + it.count);
  }
  return [...merged.entries()]
    .map(([suit, count]) => ({ suit, count }))
    .sort((a, b) => b.count - a.count || a.suit.localeCompare(b.suit));
}
