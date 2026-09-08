import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { getDecks } from '../../api/decks';
import { getCards } from '../../api/cards';
import { getSpreads, getSpread } from '../../api/spreads';
import { cardThumbnailUrl } from '../../api/images';
import { deckMatchesSlot, ensureHtml, slotTypes, slotTypeLabel } from '../../utils/formatting';
import RichTextViewer from '../common/RichTextViewer';
import RichTextEditor from '../common/RichTextEditor';
import SearchCombobox, { type SearchComboboxHandle } from '../common/SearchCombobox';
import type { Card, Deck, Spread, SpreadPosition, DeckSlot } from '../../types';
import './ReadingEditor.css';

export interface ReadingData {
  /** Client-side identity for React keys — lets readings be reordered
   *  or removed without adjacent readings inheriting each other's
   *  editor state. Never persisted (the save maps fields explicitly). */
  _key?: string;
  spread_id: number | null;
  spread_name: string | null;
  deck_id: number | null;
  deck_name: string | null;
  cartomancy_type: string | null;
  /** Per-reading notes; only surfaced when the entry has several
   *  readings (single-reading entries use the entry-level notes). */
  notes?: string;
  cards: Array<{
    name: string;
    reversed: boolean;
    deck_id?: number;
    deck_name?: string;
    position_index?: number;
    /** Card ID for reliable lookup even if card name changes */
    card_id?: number;
    /** Extra cards only: index of the spread position this clarifies
     *  (undefined = plain additional card) */
    clarifies?: number;
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
  /** Reorder this reading within the entry (undefined = can't move) */
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  /** Show this reading's own notes field — on for multi-reading
   *  entries (single-reading entries use the entry-level notes). */
  showNotes?: boolean;
}

export default function ReadingEditor({ value, onChange, onRemove, index, defaultDecks, onMoveUp, onMoveDown, showNotes }: ReadingEditorProps) {
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
  const [useAnyDeck, setUseAnyDeck] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);

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
            // A slot can allow several types — take the first allowed
            // type that has a valid default deck configured.
            for (const slotType of slotTypes(slot)) {
              const defaultDeckId = defaultDecks[slotType];
              if (defaultDeckId) {
                // Verify the default deck exists and matches the slot
                const deck = decks.find(d => d.id === defaultDeckId);
                if (deck && deckMatchesSlot(deck, slot)) {
                  derived[slot.key] = defaultDeckId;
                  break;
                }
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

  // When a spread is selected, normalize the cards array: one slot per
  // position (aligned by each card's stored position_index — saved
  // readings drop empty slots, so pure array order can misalign),
  // followed by any extra cards (clarifiers etc.), which are never
  // truncated.
  useEffect(() => {
    if (positions.length === 0 || value.cards.length >= positions.length) return;
    // Legacy readings stored cards without position_index; for those,
    // array order is all we have.
    const hasIndexes = value.cards.some(c => c.position_index != null);
    const base = positions.map((pos, idx) => {
      const existing = hasIndexes
        ? value.cards.find(c => c.position_index === idx)
        : value.cards[idx];
      if (existing) return existing;
      const slotKey = pos.deck_slot || deckSlots[0]?.key;
      const slotDeckId = slotKey ? slotDecks[slotKey] : undefined;
      const deck = decks.find(d => d.id === slotDeckId);
      return {
        name: '',
        reversed: false,
        position_index: idx,
        deck_id: slotDeckId,
        deck_name: deck?.name,
      };
    });
    const extrasKept = hasIndexes
      ? value.cards.filter(c => (c.position_index ?? -1) >= positions.length)
      : [];
    onChange({ ...value, cards: [...base, ...extrasKept] });
  }, [positions.length, value.cards.length]);

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
    // When selecting a card by name, also store deck info and card_id
    if (field === 'name' && slotDeckId) {
      newCards[idx].deck_id = slotDeckId;
      newCards[idx].deck_name = deck?.name;
      // Look up and store card_id so the entry survives card renames
      const selectedCard = deckCards.find(c => c.name === val);
      newCards[idx].card_id = selectedCard?.id;
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

  // ── Extra cards (clarifiers / variable-count pulls) ──
  // Cards beyond the spread's positions belong to this reading only —
  // the spread definition is untouched. Each may optionally mark which
  // position it clarifies.
  const extras = positions.length > 0 ? value.cards.slice(positions.length) : [];
  const extrasDeckId =
    value.deck_id ?? (deckSlots[0] ? slotDecks[deckSlots[0].key] : undefined) ?? undefined;
  const { data: extrasDeckCards = [] } = useQuery({
    queryKey: ['cards', extrasDeckId],
    queryFn: () => getCards(extrasDeckId!),
    enabled: extrasDeckId != null && positions.length > 0,
  });

  const addExtraCard = () => {
    const deck = decks.find(d => d.id === extrasDeckId);
    onChange({
      ...value,
      cards: [
        ...value.cards,
        {
          name: '',
          reversed: false,
          position_index: value.cards.length,
          deck_id: extrasDeckId,
          deck_name: deck?.name,
          _key: crypto.randomUUID(),
        },
      ],
    });
  };

  const updateExtra = (extraIdx: number, updates: Partial<ReadingData['cards'][0]>) => {
    const idx = positions.length + extraIdx;
    const newCards = [...value.cards];
    newCards[idx] = { ...newCards[idx], ...updates, position_index: idx };
    onChange({ ...value, cards: newCards });
  };

  const removeExtra = (extraIdx: number) => {
    const idx = positions.length + extraIdx;
    const newCards = value.cards
      .filter((_, i) => i !== idx)
      .map((c, i) => (i >= positions.length ? { ...c, position_index: i } : c));
    onChange({ ...value, cards: newCards });
  };

  // Combobox handles for the free-form (no spread) card list, so a
  // committed selection advances focus to the next card row.
  const freeFormRefs = useRef<Array<SearchComboboxHandle | null>>([]);

  // Same card placed more than once in this reading — physically
  // impossible with one deck, so almost certainly a mis-click. Warn,
  // never block (per-reading; reuse across readings is legitimate).
  const duplicateNames = (() => {
    const counts = new Map<string, { name: string; n: number }>();
    for (const c of value.cards) {
      if (!c.name) continue;
      const key = c.card_id != null
        ? `id:${c.deck_id ?? ''}:${c.card_id}`
        : `nm:${c.deck_id ?? ''}:${c.name}`;
      const bucket = counts.get(key) ?? { name: c.name, n: 0 };
      bucket.n += 1;
      counts.set(key, bucket);
    }
    return [...counts.values()].filter(b => b.n > 1).map(b => b.name);
  })();

  return (
    <div className="reading-editor">
      {duplicateNames.length > 0 && (
        <div className="reading-editor__dup-warning" role="alert">
          ⚠ {duplicateNames.join(', ')} appears more than once in this
          reading — double-check the positions.
        </div>
      )}
      <div className="reading-editor__header">
        <span className="reading-editor__label">Reading {index + 1}</span>
        <span className="reading-editor__header-actions">
          {(onMoveUp || onMoveDown) && (
            <>
              <button
                className="reading-editor__move-btn"
                disabled={!onMoveUp}
                onClick={onMoveUp}
                title="Move reading up"
                aria-label={`Move reading ${index + 1} up`}
              >
                ▲
              </button>
              <button
                className="reading-editor__move-btn"
                disabled={!onMoveDown}
                onClick={onMoveDown}
                title="Move reading down"
                aria-label={`Move reading ${index + 1} down`}
              >
                ▼
              </button>
            </>
          )}
          <button
            className="reading-editor__remove-btn"
            onClick={onRemove}
            title="Remove reading"
          >
            &times;
          </button>
        </span>
      </div>

      <div className="reading-editor__row">
        <div className="reading-editor__field">
          <label className="reading-editor__field-label">Spread</label>
          <SearchCombobox
            options={spreads
              .filter((s) => !s.archived || s.id === value.spread_id)
              .map((s) => ({ id: s.id, label: s.name }))}
            value={value.spread_id ?? undefined}
            placeholder="No spread — type to search…"
            onSelect={(opt) => handleSpreadChange(opt ? opt.id : null)}
          />
        </div>

        {/* Show single deck selector if no slots or single slot */}
        {!hasMultipleSlots && (
          <div className="reading-editor__field">
            <label className="reading-editor__field-label">
              {deckSlots[0] ? `Deck (${slotTypeLabel(deckSlots[0])})` : 'Deck'}
            </label>
            <SearchCombobox
              options={decks
                .filter(d => useAnyDeck || !deckSlots[0] || deckMatchesSlot(d, deckSlots[0]))
                .map((d) => ({ id: d.id, label: d.name }))}
              value={deckSlots[0] ? (slotDecks[deckSlots[0].key] ?? undefined) : (value.deck_id ?? undefined)}
              placeholder="Select deck — type to search…"
              onSelect={(opt) => {
                const deckId = opt ? opt.id : null;
                if (deckSlots[0]) {
                  handleSlotDeckChange(deckSlots[0].key, deckId);
                } else {
                  handleDeckChange(deckId);
                }
              }}
            />
          </div>
        )}
      </div>

      {value.spread_id && spread?.description ? (
        <div className="reading-editor__instructions">
          <button
            type="button"
            className="reading-editor__instructions-toggle"
            aria-expanded={instructionsOpen}
            onClick={() => setInstructionsOpen(o => !o)}
          >
            <span className={`reading-editor__instructions-chevron ${instructionsOpen ? 'reading-editor__instructions-chevron--open' : ''}`} aria-hidden="true">▸</span>
            Spread instructions
          </button>
          {instructionsOpen && (
            <div className="reading-editor__instructions-body">
              <RichTextViewer content={ensureHtml(spread.description)} />
            </div>
          )}
        </div>
      ) : null}

      {value.spread_id && (
        <label className="reading-editor__any-deck">
          <input
            type="checkbox"
            checked={useAnyDeck}
            onChange={(e) => setUseAnyDeck(e.target.checked)}
          />
          <span>Use any deck</span>
        </label>
      )}

      {/* Deck slot selectors for multi-deck spreads */}
      {hasMultipleSlots && (
        <div className="reading-editor__slots">
          {deckSlots.map((slot) => (
            <div key={slot.key} className="reading-editor__slot-row">
              <span className="reading-editor__slot-key">{slot.key}</span>
              <span className="reading-editor__slot-label">
                {slot.label || slotTypeLabel(slot)}
              </span>
              <SearchCombobox
                options={decks
                  .filter(d => useAnyDeck || deckMatchesSlot(d, slot))
                  .map((d) => ({ id: d.id, label: d.name }))}
                value={slotDecks[slot.key] ?? undefined}
                placeholder={`Select ${slotTypeLabel(slot)} deck — type to search…`}
                onSelect={(opt) => handleSlotDeckChange(slot.key, opt ? opt.id : null)}
              />
            </div>
          ))}
        </div>
      )}

      {/* Card slots */}
      <div className="reading-editor__cards">
        {positions.length > 0 ? (
          // Spread with positions: show visual canvas layout
          <>
          <VisualSpreadEditor
            positions={positions}
            cards={value.cards}
            deckSlots={deckSlots}
            slotDecks={slotDecks}
            decks={decks}
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

          {/* Extra cards: clarifiers and variable-count pulls beyond
              the spread's positions. Belong to this reading only. */}
          <div className="reading-editor__extras">
            {extras.length > 0 && (
              <div className="reading-editor__extras-title">Extra cards</div>
            )}
            {extras.map((card, ei) => (
              <div key={card._key ?? `extra-${ei}`} className="reading-editor__card-slot">
                <SearchCombobox
                  options={extrasDeckCards.map(c => cardComboOption(c, extrasDeckCards))}
                  value={
                    card.card_id
                      ?? (card.name ? extrasDeckCards.find(c => c.name === card.name)?.id : undefined)
                  }
                  disabled={extrasDeckId == null}
                  placeholder={extrasDeckId == null ? 'Select deck above' : 'Type to search cards…'}
                  onSelect={(opt) => {
                    const selected = opt ? extrasDeckCards.find(c => c.id === opt.id) : undefined;
                    updateExtra(ei, { name: selected?.name ?? '', card_id: selected?.id });
                  }}
                />
                <label className="reading-editor__reversed">
                  <input
                    type="checkbox"
                    checked={card.reversed}
                    onChange={(e) => updateExtra(ei, { reversed: e.target.checked })}
                  />
                  <span>R</span>
                </label>
                <select
                  className="reading-editor__clarifies-select"
                  value={card.clarifies ?? ''}
                  title="Which position this card clarifies (optional)"
                  onChange={(e) =>
                    updateExtra(ei, {
                      clarifies: e.target.value === '' ? undefined : Number(e.target.value),
                    })
                  }
                >
                  <option value="">Extra card</option>
                  {positions.map((pos, pi) => (
                    <option key={pi} value={pi}>
                      Clarifies {pos.key || pi + 1}{pos.label ? ` — ${pos.label}` : ''}
                    </option>
                  ))}
                </select>
                <button
                  className="reading-editor__card-remove"
                  onClick={() => removeExtra(ei)}
                  title="Remove extra card"
                >
                  &times;
                </button>
              </div>
            ))}
            <button className="reading-editor__add-card" onClick={addExtraCard}>
              + Add Card (clarifier / extra)
            </button>
          </div>
          </>
        ) : (
          // No spread: free-form card list
          <>
            {value.cards.map((card, idx) => (
              <div key={card._key ?? `card-${idx}`} className="reading-editor__card-slot">
                {deckCards.length > 0 ? (
                  <SearchCombobox
                    ref={(h) => { freeFormRefs.current[idx] = h; }}
                    options={deckCards.map(c => cardComboOption(c, deckCards))}
                    value={
                      card.card_id
                        ?? (card.name ? deckCards.find(c => c.name === card.name)?.id : undefined)
                    }
                    onSelect={(option) => {
                      const selectedCard = option
                        ? deckCards.find(c => c.id === option.id)
                        : undefined;
                      const newCards = [...value.cards];
                      newCards[idx] = {
                        ...newCards[idx],
                        name: selectedCard?.name ?? '',
                        card_id: selectedCard?.id,
                        position_index: idx,
                      };
                      onChange({ ...value, cards: newCards });
                    }}
                    onCommitted={() => freeFormRefs.current[idx + 1]?.focus()}
                  />
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

      {showNotes && (
        <div className="reading-editor__notes">
          <label className="reading-editor__notes-label">
            Notes for this reading
          </label>
          <RichTextEditor
            content={ensureHtml(value.notes || '')}
            onChange={(html) => onChange({ ...value, notes: html })}
            placeholder="Impressions specific to this spread…"
            minHeight={70}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Calculate image style for card display, handling both position rotation and card reversal.
 * When a position is rotated 90°, we need to swap the image dimensions so it fills the slot correctly.
 */
// Some decks (e.g. Terra Volatile) contain multiple distinct cards with
// the same name. Append a stable per-id suffix so each variant is
// independently selectable in <select> dropdowns. Variant order is
// driven by the cards' variant_order field when set (managed via the
// deck edit modal's Variants section) so same-name cards sharing a
// card_order can still be reliably distinguished and reordered.
type VariantCard = { id: number; name: string; variant_order?: number | null };

function compareVariants(a: VariantCard, b: VariantCard): number {
  const av = a.variant_order;
  const bv = b.variant_order;
  if (av != null && bv != null) return av - bv;
  if (av != null) return -1; // assigned variant_order sorts before unset
  if (bv != null) return 1;
  return a.id - b.id; // deterministic fallback (insertion order)
}

function labelForCard(card: VariantCard, allCards: VariantCard[]): string {
  const sameName = allCards.filter(c => c.name === card.name);
  if (sameName.length <= 1) return card.name;
  const ordered = [...sameName].sort(compareVariants);
  const variantIdx = ordered.findIndex(c => c.id === card.id) + 1;
  return `${card.name} (variant ${variantIdx})`;
}

/** Combobox option for a card: searches match the deck's own card name
 *  AND the archetype ("Ace of Wands" finds "As de Bâtons"); only the
 *  deck's own card name is displayed. */
function cardComboOption(card: Card, allCards: Card[]) {
  const archetype =
    card.archetype && card.archetype !== card.name ? card.archetype : undefined;
  return {
    id: card.id,
    label: labelForCard(card, allCards),
    keywords: archetype ? [archetype] : undefined,
  };
}

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
  decks,
  onUpdateCard,
}: {
  positions: SpreadPosition[];
  cards: ReadingData['cards'];
  deckSlots: DeckSlot[];
  slotDecks: SlotDeckMap;
  decks: Deck[];
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

  // Find card_id for a given card name within a deck. Returns the first
  // match — only used as a legacy fallback when an entry doesn't already
  // have card_id saved (newer entries store the explicit id chosen at edit
  // time, which correctly disambiguates duplicate-name variants).
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

  // One combobox handle per position, so committing a card can hop
  // focus straight to the next position — a 10-card spread becomes
  // "tow<Enter> ace<Enter> ..." with no mouse round-trips.
  const comboRefs = useRef<Array<SearchComboboxHandle | null>>([]);
  const focusNextPosition = (idx: number) => {
    comboRefs.current[idx + 1]?.focus();
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
          // Prefer the saved card_id (disambiguates same-name variants);
          // fall back to name lookup only for legacy entries.
          const cardId = card?.card_id
            ?? (card?.name ? getCardId(card.name, posDeckId) : undefined);
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
              {/* Card selector for this position. Value is the card id so
                  same-name variants (e.g. multiple "Two of Cups" in Terra
                  Volatile) are independently selectable. */}
              <SearchCombobox
                ref={(h) => { comboRefs.current[idx] = h; }}
                options={currentDeckCards.map(c => cardComboOption(c, currentDeckCards))}
                value={
                  card?.card_id
                    ?? (card?.name ? getCardId(card.name, posDeckId) : undefined)
                }
                disabled={!posDeckId}
                placeholder={posDeckId ? 'Type to search cards…' : 'Select deck above'}
                onSelect={(option) => {
                  const selectedCard = option
                    ? currentDeckCards.find(c => c.id === option.id)
                    : undefined;
                  const deck = decks.find(d => d.id === posDeckId);
                  onUpdateCard(idx, {
                    name: selectedCard?.name ?? '',
                    card_id: selectedCard?.id,
                    deck_id: posDeckId,
                    deck_name: deck?.name,
                  });
                }}
                onCommitted={() => focusNextPosition(idx)}
              />
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
