import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { getDecks } from '../../api/decks';
import { getCards } from '../../api/cards';
import { getSpreads, getSpread } from '../../api/spreads';
import { cardThumbnailUrl } from '../../api/images';
import type { Card, Deck, Spread, SpreadPosition, DeckSlot } from '../../types';
import './ReadingEditor.css';

/**
 * Check if a deck matches a required cartomancy type.
 * Supports both multi-type decks (cartomancy_types array) and legacy single-type (cartomancy_type string).
 */
function deckMatchesType(deck: Deck, requiredType: string): boolean {
  // "Any" matches all decks
  if (requiredType === 'Any') {
    return true;
  }
  // Check multi-type array first
  if (deck.cartomancy_types && deck.cartomancy_types.length > 0) {
    return deck.cartomancy_types.some(t => t.name === requiredType);
  }
  // Fall back to legacy single-type field
  return deck.cartomancy_type === requiredType;
}

export interface ReadingData {
  spread_id: number | null;
  spread_name: string | null;
  deck_id: number | null;
  deck_name: string | null;
  cartomancy_type: string | null;
  cards: Array<{
    name: string;
    reversed: boolean;
    deck_id?: number;
    deck_name?: string;
    position_index?: number;
    /** Client-side unique key for React rendering (not persisted to backend) */
    _key?: string;
  }>;
}

/** Maps deck slot keys to selected deck IDs */
type SlotDeckMap = Record<string, number>;

interface ReadingEditorProps {
  value: ReadingData;
  onChange: (data: ReadingData) => void;
  onRemove: () => void;
  index: number;
  /** Default deck IDs by cartomancy type name */
  defaultDecks?: Record<string, number | null>;
}

export default function ReadingEditor({ value, onChange, onRemove, index, defaultDecks }: ReadingEditorProps) {
  const { data: decks = [] } = useQuery({
    queryKey: ['decks'],
    queryFn: () => getDecks(),
  });

  const { data: spreads = [] } = useQuery<Spread[]>({
    queryKey: ['spreads'],
    queryFn: getSpreads,
  });

  const { data: spread } = useQuery<Spread>({
    queryKey: ['spread', value.spread_id],
    queryFn: () => getSpread(value.spread_id!),
    enabled: value.spread_id !== null && value.spread_id !== undefined,
  });

  const { data: deckCards = [] } = useQuery({
    queryKey: ['cards', value.deck_id],
    queryFn: () => getCards(value.deck_id!),
    enabled: value.deck_id !== null && value.deck_id !== undefined,
  });

  const positions: SpreadPosition[] =
    spread?.positions && Array.isArray(spread.positions) ? spread.positions : [];

  // Parse deck slots from spread
  const deckSlots: DeckSlot[] = useMemo(() => {
    if (!spread?.deck_slots) return [];
    if (Array.isArray(spread.deck_slots)) return spread.deck_slots;
    if (typeof spread.deck_slots === 'string') {
      try {
        return JSON.parse(spread.deck_slots);
      } catch {
        return [];
      }
    }
    return [];
  }, [spread?.deck_slots]);

  // Track deck assignments for each slot (derive from cards or use local state)
  const [slotDecks, setSlotDecks] = useState<SlotDeckMap>({});

  // When spread changes, reset slot deck assignments and apply defaults.
  // NOTE: We intentionally use `decks.length` instead of `decks` in the dependency array.
  // This prevents the effect from re-running when deck data refetches during editing,
  // which would disrupt the user's slot assignments. The tradeoff is that if a deck is
  // renamed mid-edit, the display might be slightly stale until the modal is reopened.
  // Stability during editing is more important than reactivity to external changes.
  useEffect(() => {
    if (value.spread_id && spread) {
      // Try to derive slot assignments from existing cards
      const derived: SlotDeckMap = {};
      value.cards.forEach((card, idx) => {
        const pos = positions[idx];
        const slotKey = pos?.deck_slot || deckSlots[0]?.key;
        if (slotKey && card?.deck_id && !derived[slotKey]) {
          derived[slotKey] = card.deck_id;
        }
      });

      // Apply default decks for slots that weren't derived from existing cards
      if (defaultDecks && deckSlots.length > 0) {
        for (const slot of deckSlots) {
          if (!derived[slot.key]) {
            const defaultDeckId = defaultDecks[slot.cartomancy_type];
            if (defaultDeckId) {
              // Verify the default deck exists and matches the type
              const deck = decks.find(d => d.id === defaultDeckId);
              if (deck && deckMatchesType(deck, slot.cartomancy_type)) {
                derived[slot.key] = defaultDeckId;
              }
            }
          }
        }
      }

      // For single-deck spreads without explicit slots, apply default based on spread's type
      if (defaultDecks && deckSlots.length === 0 && !value.deck_id) {
        const spreadType = spread.cartomancy_type;
        if (spreadType && defaultDecks[spreadType]) {
          const defaultDeckId = defaultDecks[spreadType];
          if (defaultDeckId) {
            const deck = decks.find(d => d.id === defaultDeckId);
            if (deck) {
              onChange({
                ...value,
                deck_id: defaultDeckId,
                deck_name: deck.name,
                cartomancy_type: deck.cartomancy_type || null,
              });
            }
          }
        }
      }

      setSlotDecks(derived);
    }
  }, [value.spread_id, spread, defaultDecks, decks.length]);

  // When spread changes, resize cards array to match positions
  useEffect(() => {
    if (positions.length > 0 && value.cards.length !== positions.length) {
      const newCards = positions.map((pos, idx) => {
        const existing = value.cards[idx];
        const slotKey = pos.deck_slot || deckSlots[0]?.key;
        const slotDeckId = slotKey ? slotDecks[slotKey] : undefined;
        const deck = decks.find(d => d.id === slotDeckId);
        return existing || {
          name: '',
          reversed: false,
          position_index: idx,
          deck_id: slotDeckId,
          deck_name: deck?.name,
        };
      });
      onChange({ ...value, cards: newCards });
    }
  }, [positions.length]);

  const handleSpreadChange = (spreadId: number | null) => {
    const selectedSpread = spreads.find(s => s.id === spreadId);
    setSlotDecks({});
    onChange({
      ...value,
      spread_id: spreadId,
      spread_name: selectedSpread?.name || null,
      cards: [],
    });
  };

  const handleDeckChange = (deckId: number | null) => {
    const selectedDeck = decks.find(d => d.id === deckId);
    onChange({
      ...value,
      deck_id: deckId,
      deck_name: selectedDeck?.name || null,
      cartomancy_type: selectedDeck?.cartomancy_type || null,
    });
  };

  // Handle changing the deck for a slot - updates all cards in that slot
  const handleSlotDeckChange = (slotKey: string, deckId: number | null) => {
    const deck = decks.find(d => d.id === deckId);
    const newSlotDecks = { ...slotDecks };
    if (deckId) {
      newSlotDecks[slotKey] = deckId;
    } else {
      delete newSlotDecks[slotKey];
    }
    setSlotDecks(newSlotDecks);

    // Update all cards that use this slot
    const newCards = value.cards.map((card, idx) => {
      const pos = positions[idx];
      const cardSlotKey = pos?.deck_slot || deckSlots[0]?.key;
      if (cardSlotKey === slotKey) {
        return {
          ...card,
          deck_id: deckId || undefined,
          deck_name: deck?.name,
          name: '', // Clear card when deck changes
        };
      }
      return card;
    });
    onChange({ ...value, cards: newCards });
  };

  const updateCard = (idx: number, field: string, val: string | boolean) => {
    const newCards = [...value.cards];
    const pos = positions[idx];
    const slotKey = pos?.deck_slot || deckSlots[0]?.key;
    const slotDeckId = slotKey ? slotDecks[slotKey] : value.deck_id;
    const deck = decks.find(d => d.id === slotDeckId);

    newCards[idx] = { ...newCards[idx], [field]: val, position_index: idx };
    // When selecting a card by name, also store deck info
    if (field === 'name' && slotDeckId) {
      newCards[idx].deck_id = slotDeckId;
      newCards[idx].deck_name = deck?.name;
    }
    onChange({ ...value, cards: newCards });
  };

  const addCard = () => {
    onChange({
      ...value,
      cards: [
        ...value.cards,
        {
          name: '',
          reversed: false,
          position_index: value.cards.length,
          deck_id: value.deck_id || undefined,
          deck_name: value.deck_name || undefined,
          _key: crypto.randomUUID(),
        },
      ],
    });
  };

  const removeCard = (idx: number) => {
    onChange({
      ...value,
      cards: value.cards.filter((_, i) => i !== idx),
    });
  };

  // Check if spread uses multi-deck slots
  const hasMultipleSlots = deckSlots.length > 1;

  return (
    <div className="reading-editor">
      <div className="reading-editor__header">
        <span className="reading-editor__label">Reading {index + 1}</span>
        <button
          className="reading-editor__remove-btn"
          onClick={onRemove}
          title="Remove reading"
        >
          &times;
        </button>
      </div>

      <div className="reading-editor__row">
        <div className="reading-editor__field">
          <label className="reading-editor__field-label">Spread</label>
          <select
            value={value.spread_id ?? ''}
            onChange={(e) => handleSpreadChange(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">No Spread</option>
            {spreads.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Show single deck selector if no slots or single slot */}
        {!hasMultipleSlots && (
          <div className="reading-editor__field">
            <label className="reading-editor__field-label">
              {deckSlots[0] ? `Deck (${deckSlots[0].cartomancy_type})` : 'Deck'}
            </label>
            <select
              value={deckSlots[0] ? (slotDecks[deckSlots[0].key] ?? '') : (value.deck_id ?? '')}
              onChange={(e) => {
                const deckId = e.target.value ? Number(e.target.value) : null;
                if (deckSlots[0]) {
                  handleSlotDeckChange(deckSlots[0].key, deckId);
                } else {
                  handleDeckChange(deckId);
                }
              }}
            >
              <option value="">Select Deck</option>
              {decks
                .filter(d => !deckSlots[0] || deckMatchesType(d, deckSlots[0].cartomancy_type))
                .map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
            </select>
          </div>
        )}
      </div>

      {/* Deck slot selectors for multi-deck spreads */}
      {hasMultipleSlots && (
        <div className="reading-editor__slots">
          {deckSlots.map((slot) => (
            <div key={slot.key} className="reading-editor__slot-row">
              <span className="reading-editor__slot-key">{slot.key}</span>
              <span className="reading-editor__slot-label">
                {slot.label || slot.cartomancy_type}
              </span>
              <select
                className="reading-editor__slot-deck"
                value={slotDecks[slot.key] ?? ''}
                onChange={(e) => handleSlotDeckChange(slot.key, e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Select {slot.cartomancy_type} Deck</option>
                {decks
                  .filter(d => deckMatchesType(d, slot.cartomancy_type))
                  .map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
              </select>
            </div>
          ))}
        </div>
      )}

      {/* Card slots */}
      <div className="reading-editor__cards">
        {positions.length > 0 ? (
          // Spread with positions: show visual canvas layout
          <VisualSpreadEditor
            positions={positions}
            cards={value.cards}
            deckSlots={deckSlots}
            slotDecks={slotDecks}
            onUpdateCard={(idx, updates) => {
              const pos = positions[idx];
              const slotKey = pos?.deck_slot || deckSlots[0]?.key;
              const slotDeckId = slotKey ? slotDecks[slotKey] : undefined;
              const deck = decks.find(d => d.id === slotDeckId);

              const newCards = [...value.cards];
              newCards[idx] = {
                ...newCards[idx],
                ...updates,
                position_index: idx,
                deck_id: updates.deck_id ?? slotDeckId,
                deck_name: updates.deck_name ?? deck?.name,
              };
              onChange({ ...value, cards: newCards });
            }}
          />
        ) : (
          // No spread: free-form card list
          <>
            {value.cards.map((card, idx) => (
              <div key={card._key ?? `card-${idx}`} className="reading-editor__card-slot">
                {deckCards.length > 0 ? (
                  <select
                    className="reading-editor__card-select"
                    value={card.name}
                    onChange={(e) => updateCard(idx, 'name', e.target.value)}
                  >
                    <option value="">— select card —</option>
                    {deckCards.map((c) => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="reading-editor__card-input"
                    type="text"
                    value={card.name}
                    onChange={(e) => updateCard(idx, 'name', e.target.value)}
                    placeholder="Card name"
                  />
                )}
                <label className="reading-editor__reversed">
                  <input
                    type="checkbox"
                    checked={card.reversed}
                    onChange={(e) => updateCard(idx, 'reversed', e.target.checked)}
                  />
                  <span>R</span>
                </label>
                <button
                  className="reading-editor__card-remove"
                  onClick={() => removeCard(idx)}
                  title="Remove card"
                >
                  &times;
                </button>
              </div>
            ))}
            <button className="reading-editor__add-card" onClick={addCard}>
              + Add Card
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Calculate image style for card display, handling both position rotation and card reversal.
 * When a position is rotated 90°, we need to swap the image dimensions so it fills the slot correctly.
 */
function getCardImageStyle(
  positionRotated: boolean | undefined,
  cardReversed: boolean | undefined,
  slotWidth: number,
  slotHeight: number,
): React.CSSProperties | undefined {
  // Calculate total rotation: position (90°) + reversed (180°)
  const rotation = (positionRotated && cardReversed) ? 270
    : positionRotated ? 90
    : cardReversed ? 180
    : 0;

  if (rotation === 0) {
    return undefined;
  }

  if (rotation === 180) {
    // Simple 180° flip - no dimension changes needed
    return { transform: 'rotate(180deg)' };
  }

  // For 90° or 270° rotation, we need to swap dimensions so the image fills the slot correctly
  // The image's layout box needs to be swapped, then rotated into place
  return {
    width: slotHeight,
    height: slotWidth,
    objectFit: 'contain' as const,
    transform: `rotate(${rotation}deg) translate(${rotation === 90 ? '0, -100%' : '-100%, 0'})`,
    transformOrigin: 'top left',
  };
}

/** Visual canvas editor for spread positions using deck slots */
function VisualSpreadEditor({
  positions,
  cards,
  deckSlots,
  slotDecks,
  onUpdateCard,
}: {
  positions: SpreadPosition[];
  cards: ReadingData['cards'];
  deckSlots: DeckSlot[];
  slotDecks: SlotDeckMap;
  onUpdateCard: (idx: number, updates: Partial<ReadingData['cards'][0]>) => void;
}) {
  // Calculate bounding box and scale to fit within a reasonable size
  const maxX = Math.max(...positions.map(p => (p.x || 0) + (p.width || 80)));
  const maxY = Math.max(...positions.map(p => (p.y || 0) + (p.height || 120)));
  // Scale to fit in ~450x350 area
  const scale = Math.min(1, 450 / maxX, 350 / maxY);

  // Get deck ID for a position based on its slot assignment
  const getDeckIdForPosition = (pos: SpreadPosition): number | undefined => {
    const slotKey = pos.deck_slot || deckSlots[0]?.key;
    return slotKey ? slotDecks[slotKey] : undefined;
  };

  // Get unique deck IDs from slot assignments
  const usedDeckIds = useMemo(() => {
    return Object.values(slotDecks).filter((id): id is number => id !== undefined);
  }, [slotDecks]);

  // Fetch cards for all used decks
  const deckCardQueries = useQueries({
    queries: usedDeckIds.map(deckId => ({
      queryKey: ['cards', deckId],
      queryFn: () => getCards(deckId),
    })),
  });

  // Build a map of deckId -> cards
  const deckCardsMap = useMemo(() => {
    const map = new Map<number, Card[]>();
    usedDeckIds.forEach((deckId, i) => {
      const data = deckCardQueries[i]?.data;
      if (data) map.set(deckId, data);
    });
    return map;
  }, [usedDeckIds, deckCardQueries]);

  // Get cards for a specific deck (or empty array)
  const getCardsForDeck = (deckId: number | undefined): Card[] => {
    if (!deckId) return [];
    return deckCardsMap.get(deckId) || [];
  };

  // Find card_id for a given card name within a deck
  const getCardId = (name: string, deckId: number | undefined): number | undefined => {
    const deckCards = getCardsForDeck(deckId);
    const found = deckCards.find(c => c.name === name);
    return found?.id;
  };

  // Get the slot for a position
  const getSlotForPosition = (pos: SpreadPosition): DeckSlot | undefined => {
    const slotKey = pos.deck_slot || deckSlots[0]?.key;
    return deckSlots.find(s => s.key === slotKey);
  };

  return (
    <div className="reading-editor__visual">
      {/* Visual canvas showing card layout */}
      <div
        className="reading-editor__canvas"
        style={{
          width: maxX * scale + 16,
          height: maxY * scale + 16,
          position: 'relative',
        }}
      >
        {/* key={idx} is safe here: positions come from the spread definition and don't change during editing */}
        {positions.map((pos, idx) => {
          const card = cards[idx];
          const posDeckId = getDeckIdForPosition(pos);
          const cardId = card?.name ? getCardId(card.name, posDeckId) : undefined;
          const slotWidth = (pos.width || 80) * scale;
          const slotHeight = (pos.height || 120) * scale;
          const slot = getSlotForPosition(pos);

          return (
            <div
              key={idx}
              className={`reading-editor__visual-slot ${card?.reversed ? 'reading-editor__visual-slot--reversed' : ''}`}
              style={{
                position: 'absolute',
                left: (pos.x || 0) * scale + 8,
                top: (pos.y || 0) * scale + 8,
                width: slotWidth,
                height: slotHeight,
              }}
              title={`${pos.label || `Position ${idx + 1}`}${card?.name ? `: ${card.name}` : ''}${slot ? ` [${slot.key}]` : ''}`}
            >
              {cardId ? (
                <img
                  className="reading-editor__visual-img"
                  src={cardThumbnailUrl(cardId)}
                  alt={card.name}
                  style={getCardImageStyle(pos.rotated, card.reversed, slotWidth, slotHeight)}
                />
              ) : (
                <div className="reading-editor__visual-placeholder">
                  <span className="reading-editor__visual-idx">{pos.key || idx + 1}</span>
                </div>
              )}
              {/* Small badge showing position key */}
              <span className="reading-editor__visual-badge">{pos.key || idx + 1}</span>
            </div>
          );
        })}
      </div>

      {/* Card selection list below canvas */}
      {/* key={idx} is safe here: positions come from the spread definition and don't change during editing */}
      <div className="reading-editor__position-list">
        {positions.map((pos, idx) => {
          const card = cards[idx];
          const posDeckId = getDeckIdForPosition(pos);
          const currentDeckCards = getCardsForDeck(posDeckId);
          const slot = getSlotForPosition(pos);

          return (
            <div key={idx} className="reading-editor__position-row">
              <span className="reading-editor__position-key">{pos.key || idx + 1}</span>
              <span className="reading-editor__position-label">
                {pos.label || `Position ${idx + 1}`}
                {deckSlots.length > 1 && slot && (
                  <span className="reading-editor__slot-badge">{slot.key}</span>
                )}
              </span>
              {/* Card selector for this position */}
              <select
                className="reading-editor__card-select"
                value={card?.name || ''}
                onChange={(e) => onUpdateCard(idx, { name: e.target.value })}
                disabled={!posDeckId}
              >
                <option value="">{posDeckId ? '— select card —' : '— select deck above —'}</option>
                {currentDeckCards.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </select>
              <label className="reading-editor__reversed">
                <input
                  type="checkbox"
                  checked={card?.reversed || false}
                  onChange={(e) => onUpdateCard(idx, { reversed: e.target.checked })}
                />
                <span>R</span>
              </label>
            </div>
          );
        })}
      </div>
    </div>
  );
}
