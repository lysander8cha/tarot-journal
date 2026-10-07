import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getCombinationMeanings,
  getCombinationPartners,
  getReversedCombinationTypes,
  setReversedCombinationTypes,
} from '../../../api/combinations';
import { MeaningsEditor } from '../../combinations/MeaningsEditor';
import { getReferenceSources } from '../../../api/referenceSources';
import { cardPreviewUrl } from '../../../api/images';
import { useToast } from '../../../context/ToastContext';
import SearchCombobox from '../../common/SearchCombobox';
import {
  useArchetypeCardList,
  type ArchetypeCardEntry,
} from '../../../utils/useArchetypeCardList';
import type { ReferenceSource, CombinationMeaning } from '../../../types';
import '../SettingsTab.css';
import './CombinationsSection.css';

/** Cartomancy types the Combinations feature supports. */
export const SUPPORTED_COMBINATION_TYPES = [
  'Tarot',
  'Petit Lenormand',
  'Playing Cards',
  'Playing Cards (Latin-suited)',
  'Playing Cards (German-suited)',
  'Kipper',
  'Vera Sibilla Italiana / Sibilla della Zingara', 'Sibylle des Salons / Sibilla Indovina',
] as const;

export type CombinationCartomancyType =
  (typeof SUPPORTED_COMBINATION_TYPES)[number];

interface CombinationsSectionProps {
  /** When non-null, pre-select these archetypes (used by the Reference deep-link). */
  initialCombination?: {
    cartomancy_type: string;
    archetype_1_id: number;
    archetype_2_id: number;
    archetype_1_reversed?: boolean;
    archetype_2_reversed?: boolean;
  };
  /** Called once after initial selection has been applied. */
  onInitialApplied?: () => void;
}

export default function CombinationsSection({
  initialCombination,
  onInitialApplied,
}: CombinationsSectionProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [cartomancyType, setCartomancyType] =
    useState<CombinationCartomancyType>('Petit Lenormand');
  const [card1Id, setCard1Id] = useState<number | null>(null);
  const [card2Id, setCard2Id] = useState<number | null>(null);
  const [card1Rev, setCard1Rev] = useState(false);
  const [card2Rev, setCard2Rev] = useState(false);
  // Two-card by default; triad mode adds a third slot.
  const [triad, setTriad] = useState(false);
  const [card3Id, setCard3Id] = useState<number | null>(null);
  const [card3Rev, setCard3Rev] = useState(false);
  const effCard3 = triad ? card3Id : null;

  // Clear the pair whenever the type changes — archetype ids don't
  // carry over across cartomancy types.
  useEffect(() => {
    setCard1Id(null);
    setCard2Id(null);
    setCard1Rev(false);
    setCard2Rev(false);
    setCard3Id(null);
    setCard3Rev(false);
  }, [cartomancyType]);

  // Apply deep-link selection once when it arrives.
  useEffect(() => {
    if (initialCombination) {
      setCartomancyType(initialCombination.cartomancy_type as CombinationCartomancyType);
      setCard1Id(initialCombination.archetype_1_id);
      setCard2Id(initialCombination.archetype_2_id);
      setCard1Rev(!!initialCombination.archetype_1_reversed);
      setCard2Rev(!!initialCombination.archetype_2_reversed);
      onInitialApplied?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCombination]);

  const { cardList, defaultDeckId } = useArchetypeCardList(cartomancyType);

  const { data: sources = [] } = useQuery<ReferenceSource[]>({
    queryKey: ['reference-sources'],
    queryFn: () => getReferenceSources(),
  });
  // Attribution should only offer sources covering this deck type.
  const typeSources = sources.filter(s => s.cartomancy_types.includes(cartomancyType));

  // Which types allow reversed cards in combinations (user setting).
  const { data: reversedTypes = [] } = useQuery<string[]>({
    queryKey: ['combination-reversed-types'],
    queryFn: getReversedCombinationTypes,
  });
  const reversalsEnabled = reversedTypes.includes(cartomancyType);
  const toggleReversals = async () => {
    const next = reversalsEnabled
      ? reversedTypes.filter(t => t !== cartomancyType)
      : [...reversedTypes, cartomancyType];
    try {
      await setReversedCombinationTypes(next);
      queryClient.invalidateQueries({ queryKey: ['combination-reversed-types'] });
      if (reversalsEnabled) {
        // Turning it off snaps the pickers back to upright.
        setCard1Rev(false);
        setCard2Rev(false);
      }
    } catch {
      showToast('Could not update the reversal setting.');
    }
  };

  // "has meanings" hints for the second/third card dropdowns
  const { data: partners2 = {} } = useQuery({
    queryKey: ['combination-partners', cartomancyType, card1Id, card1Rev, triad],
    queryFn: () => getCombinationPartners({
      cartomancyType, card1: card1Id!, card1Reversed: card1Rev, triad,
    }),
    enabled: card1Id != null,
  });
  const { data: partners3 = {} } = useQuery({
    queryKey: ['combination-partners3', cartomancyType, card1Id, card1Rev, card2Id, card2Rev],
    queryFn: () => getCombinationPartners({
      cartomancyType, card1: card1Id!, card1Reversed: card1Rev,
      triad: true, card2: card2Id, card2Reversed: card2Rev,
    }),
    enabled: triad && card1Id != null && card2Id != null,
  });

  const meaningsKey = ['combination-meanings', cartomancyType, card1Id, card1Rev, card2Id, card2Rev, effCard3, card3Rev];
  const { data: meanings = [] } = useQuery<CombinationMeaning[]>({
    queryKey: meaningsKey,
    queryFn: () => getCombinationMeanings(cartomancyType, card1Id!, card2Id!, card1Rev, card2Rev, effCard3, card3Rev),
    enabled: card1Id != null && card2Id != null && card1Id !== card2Id
      && (!triad || (card3Id != null && card3Id !== card1Id && card3Id !== card2Id)),
  });
  const invalidateMeanings = () =>
    queryClient.invalidateQueries({ queryKey: meaningsKey });

  return (
    <div className="settings-tab__scroll">
      <h2 className="settings-tab__title">Combinations</h2>
      <p className="settings-tab__hint">
        Reference meanings for any ordered pair of cards. The order matters —
        in Lenormand, for instance, Dog + Ring reads differently from Ring + Dog.
      </p>
      <p className="settings-tab__hint">
        Sources are managed in <strong>Reference Sources</strong>. Pick from
        them when adding a meaning below.
      </p>

      <section className="settings-tab__section">
        <h3 className="settings-tab__section-title">Combinations</h3>

        <div className="combinations__type-row">
          <label className="settings-tab__label">Cartomancy type</label>
          <select
            value={cartomancyType}
            onChange={e => setCartomancyType(e.target.value as CombinationCartomancyType)}
          >
            {SUPPORTED_COMBINATION_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <label className="combinations__reversal-toggle" title="When on, combinations for this deck type can involve reversed cards — each is its own combination with its own meanings.">
            <input
              type="checkbox"
              checked={reversalsEnabled}
              onChange={toggleReversals}
            />
            <span>Reversed cards for this type</span>
          </label>
          <div className="combinations__count-toggle" role="group" aria-label="Combination size">
            <button
              type="button"
              className={!triad ? 'combinations__count-btn--active' : ''}
              onClick={() => setTriad(false)}
            >
              Two cards
            </button>
            <button
              type="button"
              className={triad ? 'combinations__count-btn--active' : ''}
              onClick={() => setTriad(true)}
            >
              Three cards
            </button>
          </div>
        </div>

        {defaultDeckId == null && (
          <p className="combinations__warn">
            No default {cartomancyType} deck is set. Card thumbnails come from
            the default deck — set one in <strong>General</strong> settings
            to see them here.
          </p>
        )}

        <div className="combinations__pickers">
          <CardPicker
            label="First card"
            value={card1Id}
            onChange={setCard1Id}
            cardList={cardList}
            excludeIds={[card2Id, effCard3]}
            reversed={card1Rev}
            onReversedChange={reversalsEnabled ? setCard1Rev : undefined}
          />
          <CardPicker
            label="Second card"
            value={card2Id}
            onChange={setCard2Id}
            cardList={cardList}
            populated={partners2}
            excludeIds={[card1Id, effCard3]}
            reversed={card2Rev}
            onReversedChange={reversalsEnabled ? setCard2Rev : undefined}
          />
          {triad && (
            <CardPicker
              label="Third card"
              value={card3Id}
              onChange={setCard3Id}
              cardList={cardList}
              populated={partners3}
              excludeIds={[card1Id, card2Id]}
              reversed={card3Rev}
              onReversedChange={reversalsEnabled ? setCard3Rev : undefined}
            />
          )}
        </div>

        {card1Id != null && card2Id != null && card1Id !== card2Id
          && (!triad || (card3Id != null && card3Id !== card1Id && card3Id !== card2Id)) && (
          <MeaningsEditor
            cartomancyType={cartomancyType}
            card1Id={card1Id}
            card2Id={card2Id}
            card1Rev={card1Rev}
            card2Rev={card2Rev}
            card3Id={effCard3}
            card3Rev={card3Rev}
            meanings={meanings}
            sources={typeSources}
            onChanged={invalidateMeanings}
            showToast={showToast}
          />
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card picker
// ---------------------------------------------------------------------------

function CardPicker({
  label,
  value,
  onChange,
  cardList,
  excludeIds,
  reversed = false,
  onReversedChange,
  populated,
}: {
  label: string;
  value: number | null;
  onChange: (id: number | null) => void;
  cardList: ArchetypeCardEntry[];
  excludeIds: (number | null)[];
  reversed?: boolean;
  /** archetype id -> authored meaning count, for dropdown hints. */
  populated?: Record<string, number>;
  /** Present only when the type allows reversed combinations. */
  onReversedChange?: (reversed: boolean) => void;
}) {
  const selected = value != null ? cardList.find(c => c.archetypeId === value) : null;
  return (
    <div className="combinations__picker">
      <label className="settings-tab__label">{label}</label>
      <SearchCombobox
        options={cardList
          .filter(c => !excludeIds.includes(c.archetypeId))
          .map(c => {
            const count = populated?.[String(c.archetypeId)];
            return {
              id: c.archetypeId,
              label: c.rank ? `${c.rank} · ${c.name}` : c.name,
              keywords: [c.name],
              hint: count ? `${count} meaning${count === 1 ? '' : 's'}` : undefined,
            };
          })}
        value={value ?? undefined}
        onSelect={opt => onChange(opt ? opt.id : null)}
        placeholder="Type to search cards…"
      />
      {onReversedChange && (
        <label className="combinations__reversed-check">
          <input
            type="checkbox"
            checked={reversed}
            onChange={e => onReversedChange(e.target.checked)}
          />
          <span>Reversed</span>
        </label>
      )}
      <div className={`combinations__picker-image ${reversed ? 'combinations__picker-image--reversed' : ''}`}>
        {selected?.cardId ? (
          <img src={cardPreviewUrl(selected.cardId)} alt={selected.name} />
        ) : selected ? (
          <div className="combinations__placeholder">{selected.name}</div>
        ) : (
          <div className="combinations__placeholder">No selection</div>
        )}
      </div>
    </div>
  );
}
