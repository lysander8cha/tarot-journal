import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getArchetypes, type Archetype } from '../../../api/correspondences';
import { getCartomancyTypes } from '../../../api/decks';
import type { CartomancyType } from '../../../types';
import ArchetypeLanguagesTab from './archetype-tabs/ArchetypeLanguagesTab';
import ArchetypeCorrespondencesTab from './archetype-tabs/ArchetypeCorrespondencesTab';
import ArchetypeNotesTab from './archetype-tabs/ArchetypeNotesTab';
import ArchetypeCompareTab from './archetype-tabs/ArchetypeCompareTab';
import './ArchetypesViewer.css';

type SubTabId = 'languages' | 'correspondences' | 'notes' | 'compare';

const SUB_TABS: { id: SubTabId; label: string }[] = [
  { id: 'languages', label: 'Languages' },
  { id: 'correspondences', label: 'Correspondences' },
  { id: 'notes', label: 'Notes' },
  { id: 'compare', label: 'Compare' },
];

// Cartomancy types we currently support in the Archetypes viewer.
// Anything in cartomancy_types not on this list is skipped from the dropdown.
const SUPPORTED_TYPES = [
  'Tarot', 'Petit Lenormand', 'Playing Cards', 'Kipper', 'I Ching',
  'Playing Cards (Latin-suited)', 'Playing Cards (German-suited)', 'Oracle Belline', 'Vera Sibilla Italiana / Sibilla della Zingara', 'Sibylle des Salons / Sibilla Indovina',
];

interface ArchetypesViewerProps {
  /** Navigate to a Settings section with optional payload (deep-link). */
  onNavigateToSettings?: (
    section: string,
    payload?: { archetypeId?: number; fieldId?: number },
  ) => void;
  /** Archetype to select on arrival (set by the command palette). */
  pendingArchetype?: { id: number; cartomancyType: string } | null;
  onPendingArchetypeHandled?: () => void;
}

const STORAGE = {
  cartomancyType: 'archetypes-viewer.cartomancy-type',
  archetypeId: 'archetypes-viewer.archetype-id',
  subTab: 'archetypes-viewer.sub-tab',
};

export default function ArchetypesViewer({
  onNavigateToSettings,
  pendingArchetype,
  onPendingArchetypeHandled,
}: ArchetypesViewerProps) {
  // === Cartomancy types ===
  const { data: allTypes = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const supportedTypes = useMemo(
    () => allTypes.filter(t => SUPPORTED_TYPES.includes(t.name)),
    [allTypes],
  );

  const [cartomancyType, setCartomancyType] = useState<string>(() => {
    return localStorage.getItem(STORAGE.cartomancyType) || 'Tarot';
  });
  useEffect(() => {
    localStorage.setItem(STORAGE.cartomancyType, cartomancyType);
  }, [cartomancyType]);

  // === Archetype list for the active type ===
  const { data: archetypes = [] } = useQuery<Archetype[]>({
    queryKey: ['archetypes', cartomancyType],
    queryFn: () => getArchetypes(cartomancyType),
  });
  const sortedArchetypes = useMemo(
    () =>
      [...archetypes].sort((a, b) => {
        const ar = parseInt(a.rank || '0', 10);
        const br = parseInt(b.rank || '0', 10);
        return ar - br;
      }),
    [archetypes],
  );

  const [archetypeId, setArchetypeId] = useState<number | null>(() => {
    const saved = localStorage.getItem(STORAGE.archetypeId);
    return saved ? Number(saved) : null;
  });
  useEffect(() => {
    if (archetypeId != null) {
      localStorage.setItem(STORAGE.archetypeId, String(archetypeId));
    }
  }, [archetypeId]);

  // If the saved archetype isn't valid for the current type, default to first.
  useEffect(() => {
    if (sortedArchetypes.length === 0) return;
    if (!archetypeId || !sortedArchetypes.some(a => a.id === archetypeId)) {
      setArchetypeId(sortedArchetypes[0].id);
    }
  }, [sortedArchetypes, archetypeId]);

  // Command-palette deep link: jump straight to a card. Type first,
  // then the id — the invalid-for-type fallback effect leaves a valid
  // id alone once the new type's archetypes load.
  useEffect(() => {
    if (!pendingArchetype) return;
    setCartomancyType(pendingArchetype.cartomancyType);
    setArchetypeId(pendingArchetype.id);
    onPendingArchetypeHandled?.();
  }, [pendingArchetype, onPendingArchetypeHandled]);

  const selectedArchetype = sortedArchetypes.find(a => a.id === archetypeId) || null;

  // === Sub-tab ===
  const [subTab, setSubTab] = useState<SubTabId>(() => {
    const saved = localStorage.getItem(STORAGE.subTab);
    return SUB_TABS.some(t => t.id === saved) ? (saved as SubTabId) : 'languages';
  });
  useEffect(() => {
    localStorage.setItem(STORAGE.subTab, subTab);
  }, [subTab]);

  return (
    <div className="archetypes-viewer">
      <div className="archetypes-viewer__top">
        <div className="archetypes-viewer__top-row">
          <label className="archetypes-viewer__top-label">Type</label>
          <select
            value={cartomancyType}
            onChange={e => setCartomancyType(e.target.value)}
          >
            {supportedTypes.map(t => (
              <option key={t.id} value={t.name}>{t.name}</option>
            ))}
          </select>
        </div>
        <div className="archetypes-viewer__top-row">
          <label className="archetypes-viewer__top-label">Card</label>
          <select
            value={archetypeId ?? ''}
            onChange={e => setArchetypeId(e.target.value ? Number(e.target.value) : null)}
            disabled={sortedArchetypes.length === 0}
          >
            {sortedArchetypes.length === 0 && (
              <option value="">No archetypes for this type</option>
            )}
            {sortedArchetypes.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>

      <nav className="archetypes-viewer__sub-tabs">
        {SUB_TABS.map(t => (
          <button
            key={t.id}
            className={`archetypes-viewer__sub-tab ${subTab === t.id ? 'archetypes-viewer__sub-tab--active' : ''}`}
            onClick={() => setSubTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="archetypes-viewer__content">
        {selectedArchetype && subTab === 'languages' && (
          <ArchetypeLanguagesTab
            archetype={selectedArchetype}
            cartomancyType={cartomancyType}
            archetypes={sortedArchetypes}
            onNavigateToSettings={onNavigateToSettings}
          />
        )}
        {selectedArchetype && subTab === 'correspondences' && (
          <ArchetypeCorrespondencesTab
            archetype={selectedArchetype}
            cartomancyType={cartomancyType}
            onNavigateToSettings={onNavigateToSettings}
          />
        )}
        {selectedArchetype && subTab === 'notes' && (
          <ArchetypeNotesTab
            archetype={selectedArchetype}
            cartomancyType={cartomancyType}
            onNavigateToSettings={onNavigateToSettings}
          />
        )}
        {selectedArchetype && subTab === 'compare' && (
          <ArchetypeCompareTab
            archetype={selectedArchetype}
            cartomancyType={cartomancyType}
          />
        )}
        {!selectedArchetype && (
          <p className="archetypes-viewer__empty">Select a card to begin.</p>
        )}
      </div>
    </div>
  );
}
