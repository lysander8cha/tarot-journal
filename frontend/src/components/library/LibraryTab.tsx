import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Panel, Group, Separator } from 'react-resizable-panels';
import DeckList from './DeckList';
import CardGrid from './CardGrid';
import CardViewModal from './CardViewModal';
import CardEditModal from './CardEditModal';
import CardSearchBar, { type SearchFilters } from './CardSearchBar';
import DeckEditModal from './DeckEditModal';
import BatchEditModal from './BatchEditModal';
import ImportDeckModal from './ImportDeckModal';
import { getCards, searchCards } from '../../api/cards';
import type { Deck, Card } from '../../types';
import './LibraryTab.css';

export default function LibraryTab() {
  const [selectedDeck, setSelectedDeck] = useState<Deck | null>(null);
  const [viewingCardId, setViewingCardId] = useState<number | null>(null);
  const [editingCardId, setEditingCardId] = useState<number | null>(null);
  const [editingDeckId, setEditingDeckId] = useState<number | null>(null);
  const [activeSearch, setActiveSearch] = useState<SearchFilters | null>(null);
  const [selectedCardIds, setSelectedCardIds] = useState<Set<number>>(new Set());
  const [showBatchEdit, setShowBatchEdit] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const deckId = selectedDeck?.id ?? null;

  // Deck cards query (used when not searching)
  const { data: deckCards = [] } = useQuery({
    queryKey: ['cards', deckId],
    queryFn: () => getCards(deckId!),
    enabled: deckId !== null && activeSearch === null,
  });

  // Search query (used when search is active)
  const searchParams = activeSearch ? {
    ...activeSearch,
    ...(deckId ? { deck_id: deckId } : {}),
  } : null;

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['card-search', searchParams],
    queryFn: () => searchCards(searchParams as Record<string, string | number | boolean>),
    enabled: searchParams !== null,
  });

  // Card IDs for modal navigation come from whichever list is active
  const displayedCards = activeSearch ? (searchResults ?? []) : deckCards;
  const cardIds = displayedCards.map((c: Card) => c.id);

  const handleSearch = useCallback((filters: SearchFilters | null) => {
    setActiveSearch(filters);
  }, []);

  return (
    <div className="library-tab">
      <Group orientation="horizontal" style={{ width: '100%', height: '100%' }}>
        <Panel defaultSize="30%" minSize="20%">
          <DeckList
            selectedDeckId={deckId}
            onSelectDeck={setSelectedDeck}
            onEditDeck={setEditingDeckId}
            onImport={() => setShowImport(true)}
          />
        </Panel>
        <Separator className="resize-handle" />
        <Panel minSize="20%">
          <div className="library-tab__right-panel">
            <CardSearchBar deckId={deckId} onSearch={handleSearch} />
            <CardGrid
              deckId={deckId}
              deckName={selectedDeck?.name ?? ''}
              onCardClick={(card) => setViewingCardId(card.id)}
              searchResults={activeSearch ? (searchResults ?? []) : undefined}
              searchLoading={searchLoading}
              selectedIds={selectedCardIds}
              onSelectionChange={setSelectedCardIds}
              onBatchEdit={() => setShowBatchEdit(true)}
            />
          </div>
        </Panel>
      </Group>

      <CardViewModal
        cardId={viewingCardId}
        cardIds={cardIds}
        onClose={() => setViewingCardId(null)}
        onNavigate={setViewingCardId}
        onEdit={(id) => {
          setViewingCardId(null);
          setEditingCardId(id);
        }}
      />

      <CardEditModal
        cardId={editingCardId}
        deckId={deckId}
        cardIds={cardIds}
        onClose={() => setEditingCardId(null)}
        onSaved={() => {}}
        onNavigate={setEditingCardId}
      />

      <DeckEditModal
        deckId={editingDeckId}
        onClose={() => setEditingDeckId(null)}
        onSaved={() => {}}
      />

      {showBatchEdit && (
        <BatchEditModal
          cardIds={Array.from(selectedCardIds)}
          deckId={deckId}
          onClose={() => setShowBatchEdit(false)}
          onSaved={() => setSelectedCardIds(new Set())}
        />
      )}

      {showImport && (
        <ImportDeckModal
          onClose={() => setShowImport(false)}
          onImported={() => {}}
        />
      )}
    </div>
  );
}
