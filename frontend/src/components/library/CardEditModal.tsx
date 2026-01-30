import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getCard, updateCard, updateCardMetadata, setCardTags, setCardGroups,
  addCardCustomField, updateCardCustomField, deleteCardCustomField,
  type CardCustomField,
} from '../../api/cards';
import { getCardTags } from '../../api/tags';
import { getDeckGroups, getDeckCustomFields } from '../../api/decks';
import type { DeckCustomField } from '../../types';
import { cardPreviewUrl } from '../../api/images';
import type { Tag, CardGroup } from '../../types';
import Modal from '../common/Modal';
import RichTextEditor from '../common/RichTextEditor';
import './CardEditModal.css';

interface CardEditModalProps {
  cardId: number | null;
  deckId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

interface CardDetail {
  id: number;
  deck_id: number;
  name: string;
  image_path: string | null;
  card_order: number;
  archetype: string | null;
  rank: string | null;
  suit: string | null;
  notes: string | null;
  custom_fields: string | null;
  deck_name?: string;
  own_tags?: Tag[];
  groups?: CardGroup[];
  card_custom_fields?: CardCustomField[];
}

/** Local representation of a custom field being edited */
interface EditableField {
  /** null for new fields that haven't been saved yet */
  id: number | null;
  field_name: string;
  field_value: string;
  deleted: boolean;
  /** true if field originates from the legacy custom_fields JSON blob */
  legacy: boolean;
  /** Field type: 'text', 'dropdown', etc. */
  field_type?: string;
  /** Options for dropdown fields (parsed from JSON) */
  field_options?: string[];
}

export default function CardEditModal({ cardId, deckId, onClose, onSaved }: CardEditModalProps) {
  const queryClient = useQueryClient();

  const { data: card, isLoading } = useQuery<CardDetail>({
    queryKey: ['card-detail', cardId],
    queryFn: () => getCard(cardId!),
    enabled: cardId !== null,
  });

  const { data: allTags = [] } = useQuery({
    queryKey: ['card-tags'],
    queryFn: getCardTags,
    enabled: cardId !== null,
  });

  const { data: allGroups = [] } = useQuery({
    queryKey: ['deck-groups', deckId],
    queryFn: () => getDeckGroups(deckId!),
    enabled: deckId !== null,
  });

  // Fetch deck-level custom field definitions
  const { data: deckCustomFields = [] } = useQuery<DeckCustomField[]>({
    queryKey: ['deck-custom-fields', deckId],
    queryFn: () => getDeckCustomFields(deckId!),
    enabled: deckId !== null,
  });

  // Form state
  const [name, setName] = useState('');
  const [cardOrder, setCardOrder] = useState(0);
  const [archetype, setArchetype] = useState('');
  const [rank, setRank] = useState('');
  const [suit, setSuit] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([]);
  const [customFields, setCustomFields] = useState<EditableField[]>([]);
  const [saving, setSaving] = useState(false);

  // Reset form state when switching to a different card
  useEffect(() => {
    setName('');
    setCardOrder(0);
    setArchetype('');
    setRank('');
    setSuit('');
    setNotes('');
    setSelectedTagIds([]);
    setSelectedGroupIds([]);
    setCustomFields([]);
  }, [cardId]);

  // Populate form when card data loads
  useEffect(() => {
    if (card) {
      setName(card.name);
      setCardOrder(card.card_order);
      setArchetype(card.archetype || '');
      setRank(card.rank || '');
      setSuit(card.suit || '');
      setNotes(card.notes || '');
      setSelectedTagIds((card.own_tags || []).map(t => t.id));
      setSelectedGroupIds((card.groups || []).map(g => g.id));
      // Load legacy custom_fields JSON entries
      let legacyFields: EditableField[] = [];
      if (card.custom_fields) {
        try {
          const parsed = JSON.parse(card.custom_fields);
          legacyFields = Object.entries(parsed).map(([key, value]) => ({
            id: null,
            field_name: key,
            field_value: String(value ?? ''),
            deleted: false,
            legacy: true,
          }));
        } catch { /* ignore invalid JSON */ }
      }

      // Load table-based custom fields (existing card values)
      // For each card field, look up the deck definition to get field_type and field_options
      const tableFields: EditableField[] = (card.card_custom_fields || []).map(f => {
        // Find the deck-level definition for this field (case-insensitive match)
        const deckDef = deckCustomFields.find(
          def => def.field_name.toLowerCase() === f.field_name.toLowerCase()
        );

        // Parse field_options from deck definition (not from card field)
        let options: string[] | undefined;
        if (deckDef?.field_options) {
          try {
            options = JSON.parse(deckDef.field_options);
          } catch { /* ignore invalid JSON */ }
        }

        return {
          id: f.id,
          field_name: f.field_name,
          field_value: f.field_value || '',
          deleted: false,
          legacy: false,
          // Use field_type and field_options from deck definition
          field_type: deckDef?.field_type || f.field_type,
          field_options: options,
        };
      });

      // Build a set of field names that already have values (from legacy or table)
      const existingFieldNames = new Set([
        ...legacyFields.map(f => f.field_name.toLowerCase()),
        ...tableFields.map(f => f.field_name.toLowerCase()),
      ]);

      // Add deck-defined fields that don't have values yet
      const deckDefinedFields: EditableField[] = deckCustomFields
        .filter(def => !existingFieldNames.has(def.field_name.toLowerCase()))
        .map(def => {
          let options: string[] | undefined;
          if (def.field_options) {
            try {
              options = JSON.parse(def.field_options);
            } catch { /* ignore invalid JSON */ }
          }
          return {
            id: null,
            field_name: def.field_name,
            field_value: '',
            deleted: false,
            legacy: false,
            field_type: def.field_type,
            field_options: options,
          };
        });

      setCustomFields([...legacyFields, ...tableFields, ...deckDefinedFields]);
    }
  }, [card, deckCustomFields]);

  if (cardId === null) return null;

  const toggleTag = (tagId: number) => {
    setSelectedTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
  };

  const toggleGroup = (groupId: number) => {
    setSelectedGroupIds(prev =>
      prev.includes(groupId) ? prev.filter(id => id !== groupId) : [...prev, groupId]
    );
  };

  const updateField = (index: number, key: 'field_name' | 'field_value', value: string) => {
    setCustomFields(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [key]: value };
      return next;
    });
  };

  const removeField = (index: number) => {
    setCustomFields(prev => {
      const next = [...prev];
      if (next[index].id !== null || next[index].legacy) {
        // Mark existing or legacy field for deletion
        next[index] = { ...next[index], deleted: true };
      } else {
        // Remove new unsaved field entirely
        next.splice(index, 1);
      }
      return next;
    });
  };

  const addField = () => {
    setCustomFields(prev => [...prev, { id: null, field_name: '', field_value: '', deleted: false, legacy: false }]);
  };

  const handleSave = async () => {
    if (!card) return;
    setSaving(true);
    try {
      // Update basic info if changed
      if (name !== card.name || cardOrder !== card.card_order) {
        await updateCard(card.id, { name, card_order: cardOrder });
      }

      // Build updated legacy custom_fields object from editable fields
      const legacyObj: Record<string, string> = {};
      for (const f of customFields) {
        if (f.legacy && !f.deleted && f.field_name.trim()) {
          legacyObj[f.field_name] = f.field_value;
        }
      }
      const hasLegacyFields = Object.keys(legacyObj).length > 0;
      const newCustomFieldsJson = hasLegacyFields ? JSON.stringify(legacyObj) : null;

      // Update metadata if changed
      const metaChanged =
        archetype !== (card.archetype || '') ||
        rank !== (card.rank || '') ||
        suit !== (card.suit || '') ||
        notes !== (card.notes || '') ||
        newCustomFieldsJson !== (card.custom_fields || null);

      if (metaChanged) {
        await updateCardMetadata(card.id, {
          archetype, rank, suit, notes,
          // Send as object so backend can json.dumps it, or empty string to clear
          custom_fields: hasLegacyFields ? JSON.stringify(legacyObj) : '',
        });
      }

      // Update tags
      await setCardTags(card.id, selectedTagIds);

      // Update groups
      await setCardGroups(card.id, selectedGroupIds);

      // Handle table-based custom field changes (skip legacy fields)
      for (const field of customFields) {
        if (field.legacy) continue;
        if (field.deleted && field.id !== null) {
          // Delete existing field
          await deleteCardCustomField(field.id);
        } else if (!field.deleted && field.id === null && field.field_name.trim()) {
          // Add new field
          await addCardCustomField(card.id, {
            field_name: field.field_name,
            field_type: field.field_type || 'text',
            field_value: field.field_value,
            field_options: field.field_options,
          });
        } else if (!field.deleted && field.id !== null) {
          // Update existing field
          const original = (card.card_custom_fields || []).find(f => f.id === field.id);
          if (original && (field.field_name !== original.field_name || field.field_value !== (original.field_value || ''))) {
            await updateCardCustomField(field.id, {
              field_name: field.field_name,
              field_value: field.field_value,
            });
          }
        }
      }

      // Invalidate queries so lists refresh
      queryClient.invalidateQueries({ queryKey: ['card-detail', cardId] });
      queryClient.invalidateQueries({ queryKey: ['cards'] });
      queryClient.invalidateQueries({ queryKey: ['card-search'] });

      onSaved();
      onClose();
    } catch (err) {
      console.error('Failed to save card:', err);
    } finally {
      setSaving(false);
    }
  };

  const visibleFields = customFields.filter(f => !f.deleted);

  return (
    <Modal open={true} onClose={onClose} width={700}>
      {isLoading ? (
        <div className="card-edit__loading">Loading...</div>
      ) : card ? (
        <div className="card-edit">
          <div className="card-edit__header">
            {card.image_path && (
              <img
                className="card-edit__thumb"
                src={cardPreviewUrl(card.id)}
                alt={card.name}
              />
            )}
            <div className="card-edit__header-info">
              <h2 className="card-edit__title">Edit Card</h2>
              <p className="card-edit__deck">{card.deck_name}</p>
            </div>
          </div>

          <div className="card-edit__form">
            <div className="card-edit__section">
              <h3 className="card-edit__section-title">Basic Info</h3>
              <div className="card-edit__field">
                <label className="card-edit__label">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                />
              </div>
              <div className="card-edit__field">
                <label className="card-edit__label">Sort Order</label>
                <input
                  type="number"
                  value={cardOrder}
                  onChange={e => setCardOrder(parseInt(e.target.value) || 0)}
                  style={{ width: 80 }}
                />
              </div>
            </div>

            <div className="card-edit__section">
              <h3 className="card-edit__section-title">Classification</h3>
              <div className="card-edit__field">
                <label className="card-edit__label">Archetype</label>
                <input
                  type="text"
                  value={archetype}
                  onChange={e => setArchetype(e.target.value)}
                  placeholder="e.g. The Fool"
                />
              </div>
              <div className="card-edit__row">
                <div className="card-edit__field" style={{ flex: 1 }}>
                  <label className="card-edit__label">Rank</label>
                  <input
                    type="text"
                    value={rank}
                    onChange={e => setRank(e.target.value)}
                  />
                </div>
                <div className="card-edit__field" style={{ flex: 1 }}>
                  <label className="card-edit__label">Suit</label>
                  <input
                    type="text"
                    value={suit}
                    onChange={e => setSuit(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="card-edit__section">
              <h3 className="card-edit__section-title">Notes</h3>
              <textarea
                className="card-edit__notes"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={5}
                placeholder="Card notes..."
              />
            </div>

            <div className="card-edit__section">
              <div className="card-edit__section-header">
                <h3 className="card-edit__section-title">Custom Fields</h3>
                <button className="card-edit__add-btn" onClick={addField}>+ Add Field</button>
              </div>
              {visibleFields.length === 0 ? (
                <p className="card-edit__empty-hint">No custom fields</p>
              ) : (
                visibleFields.map((field, vi) => {
                  // Find the real index in the full array (including deleted)
                  const realIndex = customFields.indexOf(field);
                  const isDropdown = (field.field_type === 'dropdown' || field.field_type === 'select') && field.field_options && field.field_options.length > 0;

                  return (
                    <div key={field.id ?? `new-${vi}`} className="card-edit__custom-field">
                      <div className="card-edit__cf-header">
                        <input
                          type="text"
                          className="card-edit__cf-name"
                          value={field.field_name}
                          onChange={e => updateField(realIndex, 'field_name', e.target.value)}
                          placeholder="Field name"
                          readOnly={isDropdown} // Dropdown field names come from deck definition
                        />
                        <button
                          className="card-edit__cf-delete"
                          onClick={() => removeField(realIndex)}
                          title="Remove field"
                        >
                          &times;
                        </button>
                      </div>
                      <div className="card-edit__cf-editor">
                        {isDropdown ? (
                          <select
                            className="card-edit__cf-select"
                            value={field.field_value}
                            onChange={e => updateField(realIndex, 'field_value', e.target.value)}
                          >
                            <option value="">-- Select --</option>
                            {field.field_options!.map(opt => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : (
                          <RichTextEditor
                            content={field.field_value}
                            onChange={(html) => updateField(realIndex, 'field_value', html)}
                            placeholder="Enter text..."
                            minHeight={100}
                          />
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {allTags.length > 0 && (
              <div className="card-edit__section">
                <h3 className="card-edit__section-title">Tags</h3>
                <div className="card-edit__checkboxes">
                  {allTags.map(tag => (
                    <label key={tag.id} className="card-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={() => toggleTag(tag.id)}
                      />
                      <span
                        className="card-edit__tag-badge"
                        style={{ backgroundColor: tag.color }}
                      >
                        {tag.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {allGroups.length > 0 && (
              <div className="card-edit__section">
                <h3 className="card-edit__section-title">Groups</h3>
                <div className="card-edit__checkboxes">
                  {allGroups.map(group => (
                    <label key={group.id} className="card-edit__check">
                      <input
                        type="checkbox"
                        checked={selectedGroupIds.includes(group.id)}
                        onChange={() => toggleGroup(group.id)}
                      />
                      <span
                        className="card-edit__group-badge"
                        style={{ borderColor: group.color }}
                      >
                        {group.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="card-edit__footer">
            <button onClick={onClose}>Cancel</button>
            <button
              className="card-edit__save-btn"
              onClick={handleSave}
              disabled={saving || !name.trim()}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
