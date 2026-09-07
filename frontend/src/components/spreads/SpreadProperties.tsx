import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCartomancyTypes } from '../../api/decks';
import { getSpreadTags, addSpreadTag } from '../../api/tags';
import { getReferenceSources } from '../../api/referenceSources';
import { useToast } from '../../context/ToastContext';
import RichTextEditor from '../common/RichTextEditor';
import { ensureHtml, slotTypes } from '../../utils/formatting';
import type { DeckSlot, ReferenceSource, Tag } from '../../types';
import SearchCombobox from '../common/SearchCombobox';
import './SpreadProperties.css';

interface SpreadPropertiesProps {
  name: string;
  description: string;
  deckSlots: DeckSlot[];
  tagIds: number[];
  /** Reference source the spread is attributed to (null = none). */
  sourceId: number | null;
  onNameChange: (name: string) => void;
  onDescriptionChange: (desc: string) => void;
  onDeckSlotsChange: (slots: DeckSlot[]) => void;
  onTagIdsChange: (ids: number[]) => void;
  onSourceIdChange: (id: number | null) => void;
}

export default function SpreadProperties({
  name,
  description,
  deckSlots,
  tagIds,
  sourceId,
  onNameChange,
  onDescriptionChange,
  onDeckSlotsChange,
  onTagIdsChange,
  onSourceIdChange,
}: SpreadPropertiesProps) {
  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const { data: allTags = [] } = useQuery<Tag[]>({
    queryKey: ['spread-tags'],
    queryFn: getSpreadTags,
  });
  const { data: sources = [] } = useQuery<ReferenceSource[]>({
    queryKey: ['reference-sources'],
    queryFn: () => getReferenceSources(),
  });

  const toggleTag = (tagId: number) => {
    onTagIdsChange(
      tagIds.includes(tagId) ? tagIds.filter(id => id !== tagId) : [...tagIds, tagId],
    );
  };

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
      { key: getNextSlotKey(), cartomancy_type: 'Any', cartomancy_types: [] },
    ]);
  };

  const removeDeckSlot = (idx: number) => {
    onDeckSlotsChange(deckSlots.filter((_, i) => i !== idx));
  };

  const toggleSlotType = (idx: number, typeName: string) => {
    const updated = [...deckSlots];
    const current = slotTypes(updated[idx]);
    const next = current.includes(typeName)
      ? current.filter(t => t !== typeName)
      : [...current, typeName];
    updated[idx] = {
      ...updated[idx],
      cartomancy_types: next,
      // Keep the legacy single-type field coherent: exact when one
      // type is checked, permissive 'Any' otherwise.
      cartomancy_type: next.length === 1 ? next[0] : 'Any',
    };
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
        <RichTextEditor
          content={ensureHtml(description)}
          onChange={onDescriptionChange}
          placeholder="Describe the spread..."
          minHeight={160}
        />
      </div>

      <div className="spread-props__field">
        <label className="spread-props__label">Deck Slots</label>
        <div className="spread-props__hint">
          Define the deck types used in this spread. Check one or more types per
          slot — none checked means any type. Assign positions to slots in the designer.
        </div>
        <div className="spread-props__slots">
          {deckSlots.map((slot, idx) => {
            const checked = slotTypes(slot);
            return (
            <div key={slot.key} className="spread-props__slot">
              <div className="spread-props__slot-head">
                <span className="spread-props__slot-key">{slot.key}</span>
                <input
                  type="text"
                  className="spread-props__slot-label"
                  value={slot.label || ''}
                  onChange={(e) => updateSlotLabel(idx, e.target.value)}
                  placeholder="Label (optional)"
                />
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
              <div className="spread-props__slot-types">
                {types.map((t) => (
                  <label key={t.id} className="spread-props__slot-type-check">
                    <input
                      type="checkbox"
                      checked={checked.includes(t.name)}
                      onChange={() => toggleSlotType(idx, t.name)}
                    />
                    <span>{t.name}</span>
                  </label>
                ))}
                {checked.length === 0 && (
                  <span className="spread-props__slot-any">Any</span>
                )}
              </div>
            </div>
            );
          })}
          <button className="spread-props__add-slot" onClick={addDeckSlot}>
            + Add Deck Slot
          </button>
        </div>
      </div>

      <div className="spread-props__field">
        <label className="spread-props__label">Source</label>
        <div className="spread-props__hint">
          Attribute this spread to the reference source it comes from
          (manage sources in Settings → Reference Sources).
        </div>
        <SearchCombobox
          options={sources.map(s => ({ id: s.id, label: s.name }))}
          value={sourceId ?? undefined}
          onSelect={(opt) => onSourceIdChange(opt ? opt.id : null)}
          placeholder="No source"
        />
      </div>

      <div className="spread-props__field">
        <label className="spread-props__label">Tags</label>
        {allTags.length > 0 ? (
          <div className="spread-props__checks">
            {allTags.map(tag => (
              <label key={tag.id} className="spread-props__check">
                <input
                  type="checkbox"
                  checked={tagIds.includes(tag.id)}
                  onChange={() => toggleTag(tag.id)}
                />
                <span
                  className="spread-props__tag-badge"
                  style={{ backgroundColor: tag.color }}
                >
                  {tag.name}
                </span>
              </label>
            ))}
          </div>
        ) : (
          <div className="spread-props__hint">
            No spread tags yet — add one below.
          </div>
        )}
        <AddSpreadTagInline
          onCreated={(tagId) => {
            // Auto-select the freshly-created tag so the user
            // doesn't have to tick it after typing its name.
            if (!tagIds.includes(tagId)) onTagIdsChange([...tagIds, tagId]);
          }}
        />
      </div>
    </div>
  );
}

// =================================================================
// AddSpreadTagInline — lightweight form for adding a new spread tag
// from inside the editor, so users don't have to leave and visit
// Settings → Tags. Calls back with the new tag id so the parent can
// auto-select it in the checkbox list.
// =================================================================

const DEFAULT_TAG_COLOR = '#6B5B95';

function AddSpreadTagInline({ onCreated }: { onCreated: (tagId: number) => void }) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [tagName, setTagName] = useState('');
  const [color, setColor] = useState(DEFAULT_TAG_COLOR);
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setTagName('');
    setColor(DEFAULT_TAG_COLOR);
    setOpen(false);
  };

  const handleAdd = async () => {
    const trimmed = tagName.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      const { id } = await addSpreadTag({ name: trimmed, color });
      await queryClient.invalidateQueries({ queryKey: ['spread-tags'] });
      onCreated(id);
      reset();
    } catch (err) {
      console.error('Failed to add spread tag:', err);
      showToast('Could not add tag (name may already exist).');
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="spread-props__add-tag-btn"
        onClick={() => setOpen(true)}
      >
        + Add tag
      </button>
    );
  }
  return (
    <div className="spread-props__add-tag">
      <input
        autoFocus
        type="text"
        className="spread-props__add-tag-name"
        placeholder="Tag name"
        value={tagName}
        onChange={(e) => setTagName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleAdd();
          if (e.key === 'Escape') reset();
        }}
      />
      <input
        type="color"
        className="spread-props__add-tag-color"
        value={color}
        onChange={(e) => setColor(e.target.value)}
        title="Tag color"
      />
      <button type="button" onClick={handleAdd} disabled={saving || !tagName.trim()}>
        Add
      </button>
      <button type="button" onClick={reset}>Cancel</button>
    </div>
  );
}
