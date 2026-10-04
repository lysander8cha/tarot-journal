import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDecks, getCartomancyTypes } from '../../../../api/decks';
import { getCards } from '../../../../api/cards';
import { getDefaults } from '../../../../api/settings';
import { cardPreviewUrl } from '../../../../api/images';
import type { Archetype } from '../../../../api/correspondences';
import type { Deck, Card, CartomancyType } from '../../../../types';
import SearchCombobox from '../../../common/SearchCombobox';
import './ArchetypeCardImage.css';

interface Props {
  archetype: Archetype;
  cartomancyType: string;
  /** Optional className passed through to the outer container so consumers
   *  can compose layouts (e.g. side-by-side with the tab content). */
  className?: string;
}

/**
 * Shows the selected card from a deck of choice. Used as the top banner of
 * the Languages, Correspondences, and Notes sub-tabs. The deck choice is
 * remembered per cartomancy type so flipping between archetypes within the
 * same type doesn't reset the chosen deck.
 */
/** Prev/next arrows + "n / total" counter overlaid on a card image
 *  (parent must be position: relative). Renders nothing for < 2. */
export function SiblingNav({ index, count, onCycle }: {
  index: number;
  count: number;
  onCycle: (direction: -1 | 1) => void;
}) {
  if (count < 2) return null;
  return (
    <>
      <button
        type="button"
        className="archetype-card-image__sibling-btn archetype-card-image__sibling-btn--prev"
        onClick={() => onCycle(-1)}
        aria-label="Previous variant"
        title="Previous variant"
      >
        ‹
      </button>
      <button
        type="button"
        className="archetype-card-image__sibling-btn archetype-card-image__sibling-btn--next"
        onClick={() => onCycle(1)}
        aria-label="Next variant"
        title="Next variant"
      >
        ›
      </button>
      <span className="archetype-card-image__sibling-counter">
        {index + 1} / {count}
      </span>
    </>
  );
}

const STORAGE_KEY = (cartomancyType: string) =>
  `archetypes-viewer.image.deck.${cartomancyType}`;

export default function ArchetypeCardImage({ archetype, cartomancyType, className }: Props) {
  const { data: types = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const typeId = useMemo(
    () => types.find(t => t.name === cartomancyType)?.id,
    [types, cartomancyType],
  );

  const { data: decks = [] } = useQuery<Deck[]>({
    queryKey: ['decks', typeId],
    queryFn: () => getDecks(typeId),
    enabled: typeId != null,
  });

  const { data: defaults } = useQuery({
    queryKey: ['settings-defaults'],
    queryFn: getDefaults,
  });
  const defaultDeckId =
    (defaults?.default_decks && defaults.default_decks[cartomancyType]) || null;

  const [deckId, setDeckId] = useState<number | null>(null);
  useEffect(() => {
    // Re-evaluate only when the cartomancy type or available decks change —
    // not on every archetype switch, so the user's chosen deck persists as
    // they flip through cards.
    const saved = localStorage.getItem(STORAGE_KEY(cartomancyType));
    const savedNum = saved ? Number(saved) : null;
    if (savedNum && decks.some(d => d.id === savedNum)) {
      setDeckId(savedNum);
    } else if (defaultDeckId && decks.some(d => d.id === defaultDeckId)) {
      setDeckId(defaultDeckId);
    } else if (decks.length > 0) {
      setDeckId(decks[0].id);
    } else {
      setDeckId(null);
    }
  }, [cartomancyType, decks, defaultDeckId]);
  useEffect(() => {
    if (deckId != null) {
      localStorage.setItem(STORAGE_KEY(cartomancyType), String(deckId));
    }
  }, [cartomancyType, deckId]);

  const { data: deckCards = [] } = useQuery<Card[]>({
    queryKey: ['cards', deckId],
    queryFn: () => (deckId != null ? getCards(deckId) : Promise.resolve([])),
    enabled: deckId != null,
  });
  // All cards in the deck that map to this archetype — multiple in decks
  // like Terra Volatile (named variants) or Playing Cards (consolidated
  // Joker). Sorted by variant_order (nulls last by id) to match the deck
  // edit modal's Variants section.
  const matchingCards = useMemo(() => {
    return [...deckCards]
      .filter(c => c.archetype === archetype.name)
      .sort((a, b) => {
        const av = a.variant_order;
        const bv = b.variant_order;
        if (av != null && bv != null) return av - bv;
        if (av != null) return -1;
        if (bv != null) return 1;
        return a.id - b.id;
      });
  }, [deckCards, archetype.name]);
  // Reset variant index when the archetype or deck changes so flipping
  // through archetypes lands on variant 1 each time. Clamp if the count
  // shrinks (e.g. user just deleted a card).
  const [siblingIdx, setSiblingIdx] = useState(0);
  useEffect(() => {
    setSiblingIdx(0);
  }, [archetype.id, deckId]);
  const safeIdx = matchingCards.length === 0
    ? -1
    : Math.min(siblingIdx, matchingCards.length - 1);
  const matchingCard = safeIdx >= 0 ? matchingCards[safeIdx] : null;
  const cycleSibling = (direction: -1 | 1) => {
    if (matchingCards.length < 2) return;
    setSiblingIdx(i => {
      const n = matchingCards.length;
      return ((i % n) + direction + n) % n;
    });
  };

  if (decks.length === 0) {
    return (
      <aside className={`archetype-card-image ${className || ''}`}>
        <p className="archetype-card-image__empty">
          No {cartomancyType} decks in your library yet.
        </p>
      </aside>
    );
  }

  return (
    <aside className={`archetype-card-image ${className || ''}`}>
      <div className="archetype-card-image__viewer">
        {matchingCard ? (
          <img
            className="archetype-card-image__img"
            src={cardPreviewUrl(matchingCard.id)}
            alt={archetype.name}
          />
        ) : (
          <div className="archetype-card-image__placeholder">
            No matching card in this deck.
          </div>
        )}
        <SiblingNav index={safeIdx} count={matchingCards.length} onCycle={cycleSibling} />
      </div>
      <div className="archetype-card-image__deck">
        <SearchCombobox
          options={decks.map(d => ({ id: d.id, label: d.name }))}
          value={deckId ?? undefined}
          onSelect={opt => { if (opt) setDeckId(opt.id); }}
          placeholder="Type to search decks…"
        />
      </div>
    </aside>
  );
}
