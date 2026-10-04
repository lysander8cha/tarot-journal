/**
 * Traditional Lenormand-to-playing-card mapping. Each of the 36 cards has a
 * playing card "inset" shown in the corner of most Lenormand decks; correspondence
 * groupings (suit, rank) derive from this mapping.
 */
export const LENORMAND_PLAYING_CARD: Record<string, { suit: string; rank: string }> = {
  'Rider':      { suit: 'Hearts',   rank: 'Nine' },
  'Clover':     { suit: 'Diamonds', rank: 'Six' },
  'Ship':       { suit: 'Spades',   rank: 'Ten' },
  'House':      { suit: 'Hearts',   rank: 'King' },
  'Tree':       { suit: 'Hearts',   rank: 'Seven' },
  'Clouds':     { suit: 'Clubs',    rank: 'King' },
  'Snake':      { suit: 'Clubs',    rank: 'Queen' },
  'Coffin':     { suit: 'Diamonds', rank: 'Nine' },
  'Bouquet':    { suit: 'Spades',   rank: 'Queen' },
  'Scythe':     { suit: 'Diamonds', rank: 'Jack' },
  'Whip':       { suit: 'Clubs',    rank: 'Jack' },
  'Birds':      { suit: 'Diamonds', rank: 'Seven' },
  'Child':      { suit: 'Spades',   rank: 'Jack' },
  'Fox':        { suit: 'Clubs',    rank: 'Nine' },
  'Bear':       { suit: 'Clubs',    rank: 'Ten' },
  'Stars':      { suit: 'Hearts',   rank: 'Six' },
  'Stork':      { suit: 'Hearts',   rank: 'Queen' },
  'Dog':        { suit: 'Hearts',   rank: 'Ten' },
  'Tower':      { suit: 'Spades',   rank: 'Six' },
  'Garden':     { suit: 'Spades',   rank: 'Eight' },
  'Mountain':   { suit: 'Clubs',    rank: 'Eight' },
  'Crossroads': { suit: 'Diamonds', rank: 'Queen' },
  'Mice':       { suit: 'Clubs',    rank: 'Seven' },
  'Heart':      { suit: 'Hearts',   rank: 'Jack' },
  'Ring':       { suit: 'Clubs',    rank: 'Ace' },
  'Book':       { suit: 'Diamonds', rank: 'Ten' },
  'Letter':     { suit: 'Spades',   rank: 'Seven' },
  'Man':        { suit: 'Hearts',   rank: 'Ace' },
  'Woman':      { suit: 'Spades',   rank: 'Ace' },
  'Lily':       { suit: 'Spades',   rank: 'King' },
  'Sun':        { suit: 'Diamonds', rank: 'Ace' },
  'Moon':       { suit: 'Hearts',   rank: 'Eight' },
  'Key':        { suit: 'Diamonds', rank: 'Eight' },
  'Fish':       { suit: 'Diamonds', rank: 'King' },
  'Anchor':     { suit: 'Spades',   rank: 'Nine' },
  'Cross':      { suit: 'Clubs',    rank: 'Six' },
};

/** Canonical Petit Lenormand card numbers by archetype name. The
 * archetypes' rank field now holds the playing-card inset rank, so the
 * 1-36 numbering lives here. */
export const LENORMAND_NUMBERS: Record<string, string> = Object.fromEntries(
  [
    'Rider', 'Clover', 'Ship', 'House', 'Tree', 'Clouds', 'Snake', 'Coffin',
    'Bouquet', 'Scythe', 'Whip', 'Birds', 'Child', 'Fox', 'Bear', 'Stars',
    'Stork', 'Dog', 'Tower', 'Garden', 'Mountain', 'Crossroads', 'Mice',
    'Heart', 'Ring', 'Book', 'Letter', 'Man', 'Woman', 'Lily', 'Sun', 'Moon',
    'Key', 'Fish', 'Anchor', 'Cross',
  ].map((name, i) => [name, String(i + 1)]),
);

/** Playing card rank → numerology number. Court cards (Jack, Queen, King)
 * are omitted because they have no numeric equivalent. */
export const PIP_RANK_TO_NUMBER: Record<string, string> = {
  'Ace': '1',
  'Two': '2',
  'Three': '3',
  'Four': '4',
  'Five': '5',
  'Six': '6',
  'Seven': '7',
  'Eight': '8',
  'Nine': '9',
  'Ten': '10',
};

/** For a Lenormand archetype, return the numerology values to seed:
 * the card's number (1-36) plus the pip rank number for non-court cards. */
export function lenormandDefaultNumerology(
  lenormandName: string,
  cardNumber: string | null,
): string[] {
  const values: string[] = [];
  if (cardNumber) values.push(cardNumber);
  const playingRank = LENORMAND_PLAYING_CARD[lenormandName]?.rank;
  if (playingRank && PIP_RANK_TO_NUMBER[playingRank]) {
    const pipNum = PIP_RANK_TO_NUMBER[playingRank];
    if (!values.includes(pipNum)) values.push(pipNum);
  }
  return values;
}
