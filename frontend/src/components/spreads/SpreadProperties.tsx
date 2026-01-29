import { useQuery } from '@tanstack/react-query';
import { getCartomancyTypes } from '../../api/decks';
import type { DeckSlot } from '../../types';
import './SpreadProperties.css';

interface SpreadPropertiesProps {
  name: string;
  description: string;
  deckSlots: DeckSlot[];
  onNameChange: (name: string) => void;
  onDescriptionChange: (desc: string) => void;
  onDeckSlotsChange: (slots: DeckSlot[]) => void;
}

export default function SpreadProperties({
  name,
  description,
  deckSlots,
  onNameChange,
  onDescriptionChange,
  onDeckSlotsChange,
}: SpreadPropertiesProps) {
  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });

  // Generate next available slot key (A, B, C, ...)
  const getNextSlotKey = (): string => {
    const usedKeys = new Set(deckSlots.map(s => s.key));
    for (let i = 0; i < 26; i++) {
      const key = String.fromCharCode(65 + i); // A-Z
      if (!usedKeys.has(key)) return key;
    }
    return String(deckSlots.length + 1);
  };

  const addDeckSlot = () => {
    onDeckSlotsChange([
      ...deckSlots,
      { key: getNextSlotKey(), cartomancy_type: 'Any' },
    ]);
  };

  const removeDeckSlot = (idx: number) => {
    onDeckSlotsChange(deckSlots.filter((_, i) => i !== idx));
  };

  const updateSlotType = (idx: number, typeName: string) => {
    const updated = [...deckSlots];
    updated[idx] = { ...updated[idx], cartomancy_type: typeName };
    onDeckSlotsChange(updated);
  };

  const updateSlotLabel = (idx: number, label: string) => {
    const updated = [...deckSlots];
    updated[idx] = { ...updated[idx], label: label || undefined };
    onDeckSlotsChange(updated);
  };

  return (
    <div className="spread-props">
      <div className="spread-props__field">
        <label className="spread-props__label">Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Spread name"
        />
      </div>

      <div className="spread-props__field">
        <label className="spread-props__label">Description</label>
        <textarea
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          rows={3}
          placeholder="Describe the spread..."
        />
      </div>

      <div className="spread-props__field">
        <label className="spread-props__label">Deck Slots</label>
        <div className="spread-props__hint">
          Define the deck types used in this spread. Assign positions to slots in the designer.
        </div>
        <div className="spread-props__slots">
          {deckSlots.map((slot, idx) => (
            <div key={slot.key} className="spread-props__slot">
              <span className="spread-props__slot-key">{slot.key}</span>
              <input
                type="text"
                className="spread-props__slot-label"
                value={slot.label || ''}
                onChange={(e) => updateSlotLabel(idx, e.target.value)}
                placeholder="Label (optional)"
              />
              <select
                className="spread-props__slot-type"
                value={slot.cartomancy_type}
                onChange={(e) => updateSlotType(idx, e.target.value)}
              >
                <option value="Any">Any</option>
                {types.map((t) => (
                  <option key={t.id} value={t.name}>{t.name}</option>
                ))}
              </select>
              {deckSlots.length > 1 && (
                <button
                  className="spread-props__slot-remove"
                  onClick={() => removeDeckSlot(idx)}
                  title="Remove slot"
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <button className="spread-props__add-slot" onClick={addDeckSlot}>
            + Add Deck Slot
          </button>
        </div>
      </div>
    </div>
  );
}
