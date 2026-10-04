import { useState, useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDecks, getCartomancyTypes } from '../../../../api/decks';
import { getCards, getCard } from '../../../../api/cards';
import { getDefaults } from '../../../../api/settings';
import { cardPreviewUrl } from '../../../../api/images';
import { getCardCorrespondences } from '../../../../api/correspondences';
import RichTextViewer from '../../../common/RichTextViewer';
import SearchCombobox from '../../../common/SearchCombobox';
import { SiblingNav } from './ArchetypeCardImage';
import {
  CORRESPONDENCE_FIELDS,
  CORRESPONDENCE_FIELD_LABELS,
} from '../../../../types';
import type {
  Deck,
  Card,
  CartomancyType,
  ResolvedCorrespondence,
} from '../../../../types';
import type { Archetype } from '../../../../api/correspondences';
import './ArchetypeCompareTab.css';

// The card detail endpoint returns these joined extras alongside the Card row.
interface CardDetail extends Card {
  card_custom_fields?: Array<{
    field_name: string;
    field_value: string | null;
    field_type: string;
  }>;
}

function plainTextHasContent(value: string | null | undefined): boolean {
  if (!value) return false;
  return value.replace(/<[^>]*>/g, '').trim().length > 0;
}

interface Props {
  archetype: Archetype;
  cartomancyType: string;
}

// Per-side deck choice is remembered by cartomancy type so it persists as
// the user flips between archetypes within the same type. Card choice is
// not persisted — each column re-derives its default card from the parent
// archetype every time the deck or archetype changes.
const STORAGE = (which: 'left' | 'right', cartomancyType: string) =>
  `archetypes-viewer.compare.${which}.${cartomancyType}`;

export default function ArchetypeCompareTab({ archetype, cartomancyType }: Props) {
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

  // Cross-column awareness: each column publishes its current card archetype
  // upward so the other column can prefer it on a deck switch.
  const [leftArchetype, setLeftArchetype] = useState<string | null>(null);
  const [rightArchetype, setRightArchetype] = useState<string | null>(null);

  // Linked mode (default): the second card follows the first card's
  // archetype — compare the same card across decks. Unlink to pick
  // any two cards freely.
  const [linked, setLinked] = useState<boolean>(
    () => localStorage.getItem('archetypes-viewer.compare.linked') !== 'off',
  );
  const toggleLinked = (on: boolean) => {
    setLinked(on);
    localStorage.setItem('archetypes-viewer.compare.linked', on ? 'on' : 'off');
  };

  if (decks.length < 2) {
    return (
      <div className="archetype-compare archetype-compare--empty">
        Need at least two {cartomancyType} decks in your library to compare.
      </div>
    );
  }

  // Each column reports its currently-displayed card's archetype name so the
  // other column can use it as the match target on a deck switch. (When you
  // change deck B, you almost always want B to land on the same card you're
  // already looking at in column A, even if that's not the parent archetype.)
  return (
    <div>
      <div className="archetype-compare__toolbar">
        <label
          className="archetype-compare__link-toggle"
          title="By default the second column shows the same card as the first. Tick to pick any card instead."
        >
          <input
            type="checkbox"
            checked={!linked}
            onChange={e => toggleLinked(!e.target.checked)}
          />
          <span>Select different card</span>
        </label>
      </div>
      <div className="archetype-compare">
      <CompareColumn
        side="left"
        archetype={archetype}
        cartomancyType={cartomancyType}
        decks={decks}
        defaultDeckId={defaultDeckId}
        otherArchetypeName={rightArchetype}
        onSelectedArchetypeChange={setLeftArchetype}
      />
      <CompareColumn
        side="right"
        archetype={archetype}
        cartomancyType={cartomancyType}
        decks={decks}
        defaultDeckId={defaultDeckId}
        otherArchetypeName={leftArchetype}
        onSelectedArchetypeChange={setRightArchetype}
        followArchetypeName={linked ? leftArchetype : null}
      />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// One column of the comparison
// ---------------------------------------------------------------------------

function CompareColumn({
  side,
  archetype,
  cartomancyType,
  decks,
  defaultDeckId,
  otherArchetypeName,
  onSelectedArchetypeChange,
  followArchetypeName = null,
}: {
  side: 'left' | 'right';
  archetype: Archetype;
  cartomancyType: string;
  decks: Deck[];
  defaultDeckId: number | null;
  /** Archetype name currently displayed in the other column, used as match
   *  target on a deck switch so columns stay aligned. */
  otherArchetypeName: string | null;
  /** Callback to publish this column's current card archetype upward. */
  onSelectedArchetypeChange: (name: string | null) => void;
  /** When set, this column continuously mirrors the given archetype
   *  (linked mode — the right column following the left card). */
  followArchetypeName?: string | null;
}) {
  const [deckId, setDeckId] = useState<number | null>(null);
  useEffect(() => {
    // Re-evaluate only on cartomancy/decks/default changes — the deck choice
    // sticks across archetype switches.
    const saved = localStorage.getItem(STORAGE(side, cartomancyType));
    const savedNum = saved ? Number(saved) : null;
    if (savedNum && decks.some(d => d.id === savedNum)) {
      setDeckId(savedNum);
      return;
    }
    if (decks.length === 0) {
      setDeckId(null);
      return;
    }
    // Left column prefers the cartomancy type's default deck; right column
    // prefers any deck other than the default so the user sees two distinct
    // cards by default rather than the same one twice.
    if (side === 'left') {
      const left = defaultDeckId && decks.some(d => d.id === defaultDeckId)
        ? defaultDeckId
        : decks[0].id;
      setDeckId(left);
    } else {
      const otherThanDefault = decks.find(d => d.id !== defaultDeckId);
      setDeckId((otherThanDefault ?? decks[Math.min(1, decks.length - 1)]).id);
    }
  }, [cartomancyType, decks, side, defaultDeckId]);
  useEffect(() => {
    if (deckId != null) {
      localStorage.setItem(STORAGE(side, cartomancyType), String(deckId));
    }
  }, [cartomancyType, deckId, side]);

  const { data: deckCards = [] } = useQuery<Card[]>({
    queryKey: ['cards', deckId],
    queryFn: () => (deckId != null ? getCards(deckId) : Promise.resolve([])),
    enabled: deckId != null,
  });

  // Card pick: defaults are recomputed on two triggers:
  //   - parent archetype change → match parent (both columns realign).
  //   - deck change → match the *other column's* card if possible, so picking
  //     a new deck on one side lands on the same card you're already viewing
  //     on the other side. Falls back to parent archetype, then first card.
  // Manual picks are intentionally session-local — they stick until the
  // next deck/archetype change.
  //
  // otherArchetypeName is read via a ref so the other column changing its
  // pick mid-session doesn't kick this column's selection.
  const [cardId, setCardId] = useState<number | null>(null);
  const otherArchetypeRef = useRef(otherArchetypeName);
  useEffect(() => {
    otherArchetypeRef.current = otherArchetypeName;
  }, [otherArchetypeName]);

  const prevArchetypeRef = useRef(archetype.name);
  useEffect(() => {
    if (deckCards.length === 0) {
      setCardId(null);
      prevArchetypeRef.current = archetype.name;
      return;
    }
    const parentChanged = prevArchetypeRef.current !== archetype.name;
    const target = parentChanged
      ? archetype.name
      : (otherArchetypeRef.current || archetype.name);
    const match = deckCards.find(c => c.archetype === target);
    setCardId((match ?? deckCards[0]).id);
    prevArchetypeRef.current = archetype.name;
  }, [deckCards, archetype.name]);

  // Linked mode: continuously mirror the other column's archetype.
  // Only fires when the archetypes actually differ, so cycling this
  // column's art variants (same archetype) isn't fought.
  useEffect(() => {
    if (!followArchetypeName || deckCards.length === 0) return;
    const current = deckCards.find(c => c.id === cardId);
    if (current?.archetype === followArchetypeName) return;
    const match = deckCards.find(c => c.archetype === followArchetypeName);
    if (match) setCardId(match.id);
  }, [followArchetypeName, deckCards, cardId]);

  const selectedCard = useMemo(
    () => deckCards.find(c => c.id === cardId) || null,
    [deckCards, cardId],
  );

  // Siblings = other cards in this deck that share the selected card's
  // archetype. When > 1 we render left/right arrows to cycle through them
  // so users can see Terra Volatile-style art variants or Playing Cards
  // Red/Black jokers (both mapped to the same archetype) without picking
  // each from the card dropdown.
  const siblings = useMemo(() => {
    if (!selectedCard?.archetype) return [] as typeof deckCards;
    return [...deckCards]
      .filter(c => c.archetype === selectedCard.archetype)
      .sort((a, b) => {
        const av = a.variant_order;
        const bv = b.variant_order;
        if (av != null && bv != null) return av - bv;
        if (av != null) return -1;
        if (bv != null) return 1;
        return a.id - b.id;
      });
  }, [deckCards, selectedCard?.archetype]);
  const siblingIdx = selectedCard
    ? siblings.findIndex(c => c.id === selectedCard.id)
    : -1;
  const cycleSibling = (direction: -1 | 1) => {
    if (siblings.length < 2 || siblingIdx < 0) return;
    const next = (siblingIdx + direction + siblings.length) % siblings.length;
    setCardId(siblings[next].id);
  };

  // Publish this column's archetype upward so the other column can use it
  // as the match target when its deck changes.
  useEffect(() => {
    onSelectedArchetypeChange(selectedCard?.archetype ?? null);
  }, [selectedCard?.archetype, onSelectedArchetypeChange]);

  const { data: corrs = [] } = useQuery<ResolvedCorrespondence[]>({
    queryKey: ['card-correspondences', selectedCard?.id],
    queryFn: () => getCardCorrespondences(selectedCard!.id),
    enabled: selectedCard?.id != null,
  });
  const corrMap = useMemo(() => {
    const m = new Map<string, ResolvedCorrespondence>();
    for (const c of corrs) m.set(c.field_name, c);
    return m;
  }, [corrs]);

  // Full card detail for custom fields. The basic deck listing doesn't carry
  // them; we have to fetch each card individually.
  const { data: cardDetail } = useQuery<CardDetail>({
    queryKey: ['card-detail', selectedCard?.id],
    queryFn: () => getCard(selectedCard!.id),
    enabled: selectedCard?.id != null,
  });
  const customFields = useMemo(() => {
    if (!cardDetail) return [] as { field_name: string; field_value: string }[];
    // Legacy JSON blob in card.custom_fields
    let legacy: Record<string, string> = {};
    if (cardDetail.custom_fields) {
      try { legacy = JSON.parse(cardDetail.custom_fields); }
      catch { /* ignore parse errors on legacy data */ }
    }
    const legacyEntries = Object.entries(legacy)
      .filter(([_, v]) => plainTextHasContent(v))
      .map(([field_name, field_value]) => ({ field_name, field_value }));
    const tableEntries = (cardDetail.card_custom_fields || [])
      .filter(f => plainTextHasContent(f.field_value))
      .map(f => ({ field_name: f.field_name, field_value: f.field_value || '' }));
    // When the same field exists in both stores (the old-to-new
    // migration leaves the legacy JSON in place), hide the legacy
    // copy so the same name doesn't appear twice.
    const tableNamesLower = new Set(tableEntries.map(f => f.field_name.toLowerCase()));
    const dedupedLegacy = legacyEntries.filter(
      f => !tableNamesLower.has(f.field_name.toLowerCase()),
    );
    return [...dedupedLegacy, ...tableEntries];
  }, [cardDetail]);

  // Archetype source notes are deliberately NOT shown here: they're
  // per-archetype, so two columns comparing the same card would just
  // duplicate them — and they live one sub-tab away in Notes. The
  // columns compare what actually differs per deck: art,
  // correspondences, and the deck's own card fields.
  return (
    <div className="archetype-compare__col">
      <div className="archetype-compare__selectors">
        <SearchCombobox
          options={decks.map(d => ({ id: d.id, label: d.name }))}
          value={deckId ?? undefined}
          onSelect={opt => { if (opt) setDeckId(opt.id); }}
          placeholder="Type to search decks…"
        />
        <SearchCombobox
          options={deckCards.map(c => ({ id: c.id, label: c.name }))}
          value={cardId ?? undefined}
          onSelect={opt => { if (opt) setCardId(opt.id); }}
          disabled={deckCards.length === 0 || !!followArchetypeName}
          placeholder={deckCards.length === 0 ? 'No cards' : 'Type to search cards…'}
        />
      </div>

      <div className="archetype-compare__image-wrap">
        {selectedCard ? (
          <img
            className="archetype-compare__image"
            src={cardPreviewUrl(selectedCard.id)}
            alt={selectedCard.name}
          />
        ) : (
          <div className="archetype-compare__no-image">
            This deck has no cards.
          </div>
        )}
        <SiblingNav index={siblingIdx} count={siblings.length} onCycle={cycleSibling} />
      </div>

      {selectedCard && (
        <dl className="archetype-compare__corr">
          {CORRESPONDENCE_FIELDS.map(f => {
            const c = corrMap.get(f);
            const values = c?.values || [];
            if (values.length === 0) return null;
            return (
              <div key={f} className="archetype-compare__corr-row">
                <dt>{CORRESPONDENCE_FIELD_LABELS[f] || f}</dt>
                <dd>{values.join(', ')}</dd>
              </div>
            );
          })}
        </dl>
      )}

      {customFields.length > 0 && (
        <div className="archetype-compare__custom">
          {customFields.map((f, i) => (
            <div key={`${f.field_name}-${i}`} className="archetype-compare__custom-field">
              <h5>{f.field_name}</h5>
              <RichTextViewer content={f.field_value} />
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

