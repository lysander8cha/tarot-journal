import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDecks, getCartomancyTypes } from '../../api/decks';
import type { Deck } from '../../types';
import './DeckList.css';

interface DeckListProps {
  selectedDeckId: number | null;
  onSelectDeck: (deck: Deck) => void;
  onEditDeck?: (deckId: number) => void;
  onImport?: () => void;
  onExport?: (deckId: number) => void;
}

export default function DeckList({ selectedDeckId, onSelectDeck, onEditDeck, onImport }: DeckListProps) {
  const [filterTypeId, setFilterTypeId] = useState<number | undefined>(undefined);
  const [sortBy, setSortBy] = useState<'name' | 'type' | 'cards'>('name');
  const [sortAsc, setSortAsc] = useState(true);
  const [showTags, setShowTags] = useState(false);

  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });

  const { data: decks = [], isLoading } = useQuery({
    queryKey: ['decks', filterTypeId],
    queryFn: () => getDecks(filterTypeId),
  });

  const sortedDecks = [...decks].sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'name') {
      cmp = a.name.localeCompare(b.name);
    } else if (sortBy === 'type') {
      cmp = (a.cartomancy_type || '').localeCompare(b.cartomancy_type || '');
    } else if (sortBy === 'cards') {
      cmp = (a.card_count || 0) - (b.card_count || 0);
    }
    return sortAsc ? cmp : -cmp;
  });

  const handleHeaderClick = (col: 'name' | 'type' | 'cards') => {
    if (sortBy === col) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(col);
      setSortAsc(true);
    }
  };

  return (
    <div className="deck-list">
      <div className="deck-list__header">
        <h2 className="deck-list__title">Decks</h2>
        {onImport && (
          <button className="deck-list__import-btn" onClick={onImport}>Import</button>
        )}
        <label className="deck-list__tag-toggle">
          <input
            type="checkbox"
            checked={showTags}
            onChange={(e) => setShowTags(e.target.checked)}
          />
          <span>Tags</span>
        </label>
      </div>
      <div className="deck-list__filters">
        <select
          className="deck-list__filter"
          value={filterTypeId ?? ''}
          onChange={(e) => setFilterTypeId(e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">All Types</option>
          {types.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      <div className="deck-list__sort-bar">
        <span className="deck-list__sort-label">Sort:</span>
        {(['name', 'type', 'cards'] as const).map((col) => (
          <button
            key={col}
            className={`deck-list__sort-btn ${sortBy === col ? 'deck-list__sort-btn--active' : ''}`}
            onClick={() => handleHeaderClick(col)}
          >
            {col === 'cards' ? '#' : col.charAt(0).toUpperCase() + col.slice(1)}
            {sortBy === col && (sortAsc ? ' \u25B2' : ' \u25BC')}
          </button>
        ))}
      </div>

      <div className="deck-list__rows">
        {isLoading && <div className="deck-list__loading">Loading...</div>}
        {sortedDecks.map((deck) => (
          <div
            key={deck.id}
            className={`deck-list__row ${deck.id === selectedDeckId ? 'deck-list__row--selected' : ''}`}
            onClick={() => onSelectDeck(deck)}
            onDoubleClick={() => onEditDeck?.(deck.id)}
          >
            <div className="deck-list__row-content">
              <span className="deck-list__name">
                {deck.name}
                {showTags && deck.tags && deck.tags.length > 0 && (
                  <span className="deck-list__tags">
                    {deck.tags.map(t => (
                      <span
                        key={t.id}
                        className="deck-list__tag-dot"
                        style={{ backgroundColor: t.color }}
                        title={t.name}
                      />
                    ))}
                  </span>
                )}
              </span>
              <span className="deck-list__subtitle">
                {deck.cartomancy_type || 'Untyped'}
                {deck.card_count != null && ` \u00B7 ${deck.card_count} cards`}
              </span>
            </div>
            {onEditDeck && (
              <button
                className="deck-list__edit-btn"
                onClick={(e) => { e.stopPropagation(); onEditDeck(deck.id); }}
                title="Edit deck"
              >
                &#9998;
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
