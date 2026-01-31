import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Panel, Group, Separator } from 'react-resizable-panels';
import { createSpread, updateSpread, deleteSpread, cloneSpread } from '../../api/spreads';
import SpreadList from './SpreadList';
import SpreadDesigner from './SpreadDesigner';
import SpreadProperties from './SpreadProperties';
import PositionLegend from './PositionLegend';
import type { Spread, SpreadPosition, DeckSlot } from '../../types';
import './SpreadsTab.css';

export default function SpreadsTab() {
  const queryClient = useQueryClient();
  const [selectedSpread, setSelectedSpread] = useState<Spread | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const [error, setError] = useState('');

  // Local editing state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [positions, setPositions] = useState<SpreadPosition[]>([]);
  const [allowedDeckTypes, setAllowedDeckTypes] = useState<string[]>([]);
  const [defaultDeckId, setDefaultDeckId] = useState<number | null>(null);
  const [deckSlots, setDeckSlots] = useState<DeckSlot[]>([]);

  // Populate form when a spread is selected
  useEffect(() => {
    if (selectedSpread && !isNew) {
      setName(selectedSpread.name);
      setDescription(selectedSpread.description || '');
      setPositions(
        Array.isArray(selectedSpread.positions) ? selectedSpread.positions : [],
      );
      setAllowedDeckTypes(
        Array.isArray(selectedSpread.allowed_deck_types)
          ? selectedSpread.allowed_deck_types
          : [],
      );
      setDefaultDeckId(selectedSpread.default_deck_id);
      // Parse deck_slots from spread
      const slots = selectedSpread.deck_slots;
      if (Array.isArray(slots)) {
        setDeckSlots(slots);
      } else if (typeof slots === 'string') {
        try {
          setDeckSlots(JSON.parse(slots));
        } catch {
          setDeckSlots([]);
        }
      } else {
        setDeckSlots([]);
      }
      setSelectedIndex(null);
    }
  }, [selectedSpread, isNew]);

  const handleSelect = (spread: Spread) => {
    setSelectedSpread(spread);
    setIsNew(false);
  };

  const handleNew = () => {
    setSelectedSpread(null);
    setIsNew(true);
    setName('');
    setDescription('');
    setPositions([]);
    setAllowedDeckTypes([]);
    setDefaultDeckId(null);
    // Default to one deck slot with Tarot type
    setDeckSlots([{ key: 'A', cartomancy_type: 'Tarot', label: 'Main Deck' }]);
    setSelectedIndex(null);
  };

  const handleClone = async () => {
    if (!selectedSpread) return;
    setError('');
    try {
      const result = await cloneSpread(selectedSpread.id);
      queryClient.invalidateQueries({ queryKey: ['spreads'] });
      // Select the cloned spread after list refreshes
      // We'll set isNew=false and wait for the list to include it
      setSelectedSpread({
        ...selectedSpread,
        id: result.id,
        name: `Copy of ${selectedSpread.name}`,
      });
      setName(`Copy of ${selectedSpread.name}`);
      setIsNew(false);
    } catch (err) {
      console.error('Failed to clone spread:', err);
      setError('Failed to clone spread. Please try again.');
    }
  };

  const handleDelete = async () => {
    if (!selectedSpread) return;
    if (!window.confirm(`Delete "${selectedSpread.name}"? This cannot be undone.`)) return;
    setError('');
    try {
      await deleteSpread(selectedSpread.id);
      queryClient.invalidateQueries({ queryKey: ['spreads'] });
      setSelectedSpread(null);
      setIsNew(false);
    } catch (err) {
      console.error('Failed to delete spread:', err);
      setError('Failed to delete spread. Please try again.');
    }
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      if (isNew) {
        const result = await createSpread({
          name: name.trim(),
          positions,
          description: description || undefined,
          allowed_deck_types: allowedDeckTypes.length > 0 ? allowedDeckTypes : undefined,
          default_deck_id: defaultDeckId,
          deck_slots: deckSlots.length > 0 ? deckSlots : undefined,
        });
        setIsNew(false);
        // Re-select the newly created spread
        setSelectedSpread({
          id: result.id,
          name: name.trim(),
          description,
          positions,
          cartomancy_type: null,
          allowed_deck_types: allowedDeckTypes,
          default_deck_id: defaultDeckId,
          deck_slots: deckSlots,
          created_at: new Date().toISOString(),
        });
      } else if (selectedSpread) {
        await updateSpread(selectedSpread.id, {
          name: name.trim(),
          positions,
          description: description || undefined,
          allowed_deck_types: allowedDeckTypes.length > 0 ? allowedDeckTypes : null,
          default_deck_id: defaultDeckId,
          clear_default_deck: defaultDeckId === null && selectedSpread.default_deck_id !== null,
          deck_slots: deckSlots.length > 0 ? deckSlots : null,
        });
        setSelectedSpread({
          ...selectedSpread,
          name: name.trim(),
          description,
          positions,
          allowed_deck_types: allowedDeckTypes,
          default_deck_id: defaultDeckId,
          deck_slots: deckSlots,
        });
      }
      queryClient.invalidateQueries({ queryKey: ['spreads'] });
    } catch (err) {
      console.error('Failed to save spread:', err);
      setError('Failed to save spread. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const hasSelection = selectedSpread !== null || isNew;

  return (
    <div className="spreads-tab">
      <Group orientation="horizontal" style={{ width: '100%', height: '100%' }}>
        <Panel defaultSize="30%" minSize="20%">
          <SpreadList
            selectedSpreadId={selectedSpread?.id ?? null}
            onSelect={handleSelect}
            onNew={handleNew}
            onClone={handleClone}
            onDelete={handleDelete}
          />
        </Panel>
        <Separator className="resize-handle" />
        <Panel minSize="30%">
          {hasSelection ? (
            <div className="spreads-tab__editor">
              {error && <div className="spreads-tab__error">{error}</div>}
              <div className="spreads-tab__editor-scroll">
                <div className="spreads-tab__props-section">
                  <SpreadProperties
                    name={name}
                    description={description}
                    deckSlots={deckSlots}
                    onNameChange={setName}
                    onDescriptionChange={setDescription}
                    onDeckSlotsChange={setDeckSlots}
                  />
                </div>

                <div className="spreads-tab__designer-section">
                  <h3 className="spreads-tab__section-title">Designer</h3>
                  <SpreadDesigner
                    positions={positions}
                    onChange={setPositions}
                    selectedIndex={selectedIndex}
                    onSelectIndex={setSelectedIndex}
                    deckSlots={deckSlots}
                  />
                </div>

                <div className="spreads-tab__legend-section">
                  <PositionLegend
                    positions={positions}
                    selectedIndex={selectedIndex}
                    onSelectIndex={setSelectedIndex}
                  />
                </div>
              </div>

              <div className="spreads-tab__footer">
                <button
                  className="spreads-tab__save-btn"
                  onClick={handleSave}
                  disabled={saving || !name.trim()}
                >
                  {saving ? 'Saving...' : isNew ? 'Create Spread' : 'Save Spread'}
                </button>
              </div>
            </div>
          ) : (
            <div className="spreads-tab__empty">
              Select a spread from the list, or click "New" to create one.
            </div>
          )}
        </Panel>
      </Group>
    </div>
  );
}
