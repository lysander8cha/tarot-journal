import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getEntry,
  createEntry,
  updateEntry,
  addEntryReading,
  deleteEntryReadings,
  setEntryTags,
  setEntryQuerents,
  getProfiles,
} from '../../api/entries';
import { getEntryTags as getAllEntryTags } from '../../api/tags';
import { getDefaults, type AppDefaults } from '../../api/settings';
import Modal from '../common/Modal';
import RichTextEditor from '../common/RichTextEditor';
import ReadingEditor, { type ReadingData } from './ReadingEditor';
import type { JournalEntryFull, Tag, Profile } from '../../types';
import './EntryEditorModal.css';

interface InitialFormState {
  title: string;
  dateMode: 'now' | 'custom';
  readingDatetime: string;
  locationName: string;
  querentIds: number[];
  readerId: number | null;
  content: string;
  readings: ReadingData[];
  selectedTagIds: number[];
}

interface EntryEditorModalProps {
  entryId: number | null; // null = creating new entry
  open: boolean;
  onClose: () => void;
  onSaved: (entryId: number) => void;
}

function emptyReading(): ReadingData {
  return {
    spread_id: null,
    spread_name: null,
    deck_id: null,
    deck_name: null,
    cartomancy_type: null,
    cards: [],
  };
}

function nowLocalISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function EntryEditorModal({ entryId, open, onClose, onSaved }: EntryEditorModalProps) {
  const queryClient = useQueryClient();
  const isEditing = entryId !== null;

  // Load existing entry if editing
  const { data: existingEntry } = useQuery<JournalEntryFull>({
    queryKey: ['entry', entryId],
    queryFn: () => getEntry(entryId!),
    enabled: isEditing && open,
  });

  const { data: allTags = [] } = useQuery<Tag[]>({
    queryKey: ['entry-tags'],
    queryFn: getAllEntryTags,
    enabled: open,
  });

  const { data: profiles = [] } = useQuery<Profile[]>({
    queryKey: ['profiles'],
    queryFn: getProfiles,
    enabled: open,
  });

  const { data: defaults } = useQuery<AppDefaults>({
    queryKey: ['defaults'],
    queryFn: getDefaults,
    enabled: open,
  });

  // Form state
  const [title, setTitle] = useState('');
  const [dateMode, setDateMode] = useState<'now' | 'custom'>('now');
  const [readingDatetime, setReadingDatetime] = useState(nowLocalISO());
  const [locationName, setLocationName] = useState('');
  const [querentIds, setQuerentIds] = useState<number[]>([]);
  const [readerId, setReaderId] = useState<number | null>(null);
  const [content, setContent] = useState('');
  const [readings, setReadings] = useState<ReadingData[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track initial form state for dirty checking
  const initialStateRef = useRef<InitialFormState | null>(null);

  // Populate form when editing
  useEffect(() => {
    if (isEditing && existingEntry && !initialized) {
      const titleVal = existingEntry.title || '';
      const dateModeVal: 'now' | 'custom' = existingEntry.reading_datetime ? 'custom' : 'now';
      const datetimeVal = existingEntry.reading_datetime
        ? existingEntry.reading_datetime.replace(' ', 'T').slice(0, 16)
        : nowLocalISO();
      const locationVal = existingEntry.location_name || '';
      // Use querents array, or fall back to legacy querent_id if empty
      const querentIdsVal = existingEntry.querents?.length
        ? existingEntry.querents.map(q => q.id)
        : (existingEntry.querent_id ? [existingEntry.querent_id] : []);
      const readerVal = existingEntry.reader_id;
      const contentVal = existingEntry.content || '';
      const tagIds = existingEntry.tags.map(t => t.id);

      // Convert existing readings to ReadingData
      const readingData: ReadingData[] = existingEntry.readings.map(r => ({
        spread_id: r.spread_id,
        spread_name: r.spread_name,
        deck_id: r.deck_id,
        deck_name: r.deck_name,
        cartomancy_type: r.cartomancy_type,
        cards: (r.cards_used || []).map((c, idx) => ({
          name: c.name,
          reversed: c.reversed || false,
          deck_id: c.deck_id,
          deck_name: c.deck_name,
          position_index: c.position_index ?? idx,
        })),
      }));

      setTitle(titleVal);
      setDateMode(dateModeVal);
      setReadingDatetime(datetimeVal);
      setLocationName(locationVal);
      setQuerentIds(querentIdsVal);
      setReaderId(readerVal);
      setContent(contentVal);
      setSelectedTagIds(tagIds);
      setReadings(readingData.length > 0 ? readingData : []);

      // Store initial state for dirty checking
      initialStateRef.current = {
        title: titleVal,
        dateMode: dateModeVal,
        readingDatetime: datetimeVal,
        locationName: locationVal,
        querentIds: querentIdsVal,
        readerId: readerVal,
        content: contentVal,
        readings: readingData.length > 0 ? readingData : [],
        selectedTagIds: tagIds,
      };

      setInitialized(true);
    }
  }, [existingEntry, isEditing, initialized]);

  // Reset form when modal opens for new entry
  useEffect(() => {
    if (open && !isEditing) {
      const datetimeVal = nowLocalISO();
      // Apply defaults for reader and querent
      const defaultReader = defaults?.default_reader ?? null;
      const defaultQuerent = defaults?.default_querent_same_as_reader
        ? defaultReader
        : (defaults?.default_querent ?? null);
      const defaultQuerentIds = defaultQuerent ? [defaultQuerent] : [];

      setTitle('');
      setDateMode('now');
      setReadingDatetime(datetimeVal);
      setLocationName('');
      setReaderId(defaultReader);
      setQuerentIds(defaultQuerentIds);
      setContent('');
      setReadings([]);
      setSelectedTagIds([]);
      setInitialized(false);
      setError(null);

      // Store initial state for dirty checking (empty for new entry)
      initialStateRef.current = {
        title: '',
        dateMode: 'now',
        readingDatetime: datetimeVal,
        locationName: '',
        querentIds: defaultQuerentIds,
        readerId: defaultReader,
        content: '',
        readings: [],
        selectedTagIds: [],
      };
    }
    if (open && isEditing) {
      setInitialized(false);
      setError(null);
    }
  }, [open, entryId, defaults]);

  const toggleTag = (tagId: number) => {
    setSelectedTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
  };

  const addReading = () => {
    setReadings(prev => [...prev, emptyReading()]);
  };

  const updateReading = (idx: number, data: ReadingData) => {
    setReadings(prev => prev.map((r, i) => (i === idx ? data : r)));
  };

  const removeReading = (idx: number) => {
    setReadings(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const datetime = dateMode === 'now' ? new Date().toISOString() : readingDatetime;
      // Filter out any unselected querents (value 0)
      const validQuerentIds = querentIds.filter(id => id > 0);

      const entryData = {
        title: title.trim() || undefined,
        content: content || undefined,
        reading_datetime: datetime || undefined,
        location_name: locationName.trim() || undefined,
        // Legacy querent_id: first querent or null
        querent_id: validQuerentIds.length > 0 ? validQuerentIds[0] : null,
        reader_id: readerId,
      };

      let savedEntryId: number;

      if (isEditing) {
        await updateEntry(entryId!, entryData);
        savedEntryId = entryId!;

        // Replace readings: delete old ones, add new
        await deleteEntryReadings(savedEntryId);
      } else {
        const result = await createEntry(entryData);
        savedEntryId = result.id;
      }

      // Add readings
      for (let i = 0; i < readings.length; i++) {
        const r = readings[i];
        const cardsUsed = r.cards
          .filter(c => c.name.trim())
          .map(c => ({
            name: c.name,
            reversed: c.reversed,
            deck_id: c.deck_id,
            deck_name: c.deck_name,
            position_index: c.position_index,
          }));

        await addEntryReading(savedEntryId, {
          spread_id: r.spread_id,
          spread_name: r.spread_name || undefined,
          deck_id: r.deck_id,
          deck_name: r.deck_name || undefined,
          cartomancy_type: r.cartomancy_type || undefined,
          cards_used: cardsUsed,
          position_order: i,
        });
      }

      // Set tags
      await setEntryTags(savedEntryId, selectedTagIds);

      // Set querents
      await setEntryQuerents(savedEntryId, validQuerentIds);

      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ['entries'] });
      queryClient.invalidateQueries({ queryKey: ['entry-search'] });
      queryClient.invalidateQueries({ queryKey: ['entry', savedEntryId] });

      onSaved(savedEntryId);
      onClose();
    } catch (err) {
      console.error('Failed to save entry:', err);
      const message = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(`Failed to save entry: ${message}`);
    } finally {
      setSaving(false);
    }
  };

  // Compute whether form has unsaved changes
  const isDirty = useMemo(() => {
    const initial = initialStateRef.current;
    if (!initial) return false;

    // Compare simple fields
    if (title !== initial.title) return true;
    if (dateMode !== initial.dateMode) return true;
    if (dateMode === 'custom' && readingDatetime !== initial.readingDatetime) return true;
    if (locationName !== initial.locationName) return true;
    if (readerId !== initial.readerId) return true;
    if (content !== initial.content) return true;

    // Compare querent selections
    if (querentIds.length !== initial.querentIds.length) return true;
    if (!querentIds.every((id, idx) => initial.querentIds[idx] === id)) return true;

    // Compare tag selections
    if (selectedTagIds.length !== initial.selectedTagIds.length) return true;
    if (!selectedTagIds.every(id => initial.selectedTagIds.includes(id))) return true;

    // Compare readings (deep comparison via JSON)
    if (JSON.stringify(readings) !== JSON.stringify(initial.readings)) return true;

    return false;
  }, [title, dateMode, readingDatetime, locationName, querentIds, readerId, content, selectedTagIds, readings]);

  if (!open) return null;

  return (
    <Modal open={true} onClose={onClose} width={800} isDirty={isDirty}>
      <div className="entry-editor">
        <h2 className="entry-editor__title">
          {isEditing ? 'Edit Entry' : 'New Journal Entry'}
        </h2>

        <div className="entry-editor__form">
          {/* Title */}
          <div className="entry-editor__field">
            <label className="entry-editor__label">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Entry title (optional)"
            />
          </div>

          {/* Date/Time */}
          <div className="entry-editor__field">
            <label className="entry-editor__label">Date &amp; Time</label>
            <div className="entry-editor__date-row">
              <label className="entry-editor__radio">
                <input
                  type="radio"
                  name="dateMode"
                  checked={dateMode === 'now'}
                  onChange={() => setDateMode('now')}
                />
                <span>Now</span>
              </label>
              <label className="entry-editor__radio">
                <input
                  type="radio"
                  name="dateMode"
                  checked={dateMode === 'custom'}
                  onChange={() => setDateMode('custom')}
                />
                <span>Custom</span>
              </label>
              {dateMode === 'custom' && (
                <input
                  type="datetime-local"
                  value={readingDatetime}
                  onChange={(e) => setReadingDatetime(e.target.value)}
                  className="entry-editor__datetime-input"
                />
              )}
            </div>
          </div>

          {/* Location */}
          <div className="entry-editor__field">
            <label className="entry-editor__label">Location</label>
            <input
              type="text"
              value={locationName}
              onChange={(e) => setLocationName(e.target.value)}
              placeholder="Where the reading took place (optional)"
            />
          </div>

          {/* Querents / Reader */}
          {profiles.length > 0 && (
            <div className="entry-editor__row">
              <div className="entry-editor__field entry-editor__field--querents">
                <div className="entry-editor__querents-header">
                  <label className="entry-editor__label">Querent{querentIds.length !== 1 ? 's' : ''}</label>
                  <button
                    type="button"
                    className="entry-editor__add-querent-btn"
                    onClick={() => setQuerentIds(prev => [...prev, 0])}
                  >
                    + Add Querent
                  </button>
                </div>
                {querentIds.length === 0 ? (
                  <div className="entry-editor__no-querents">No querents selected</div>
                ) : (
                  <div className="entry-editor__querents-list">
                    {querentIds.map((qId, idx) => (
                      <div key={idx} className="entry-editor__querent-row">
                        <select
                          value={qId || ''}
                          onChange={(e) => {
                            const newId = e.target.value ? Number(e.target.value) : 0;
                            setQuerentIds(prev => prev.map((id, i) => i === idx ? newId : id));
                          }}
                        >
                          <option value="">Select a profile...</option>
                          {profiles.map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="entry-editor__remove-querent-btn"
                          onClick={() => setQuerentIds(prev => prev.filter((_, i) => i !== idx))}
                          title="Remove querent"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="entry-editor__field">
                <label className="entry-editor__label">Reader</label>
                <select
                  value={readerId ?? ''}
                  onChange={(e) => setReaderId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">None</option>
                  {profiles
                    .filter((p) => !p.querent_only)
                    .map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                </select>
              </div>
            </div>
          )}

          {/* Readings */}
          <div className="entry-editor__section">
            <div className="entry-editor__section-header">
              <h3 className="entry-editor__section-title">Readings</h3>
              <button className="entry-editor__add-btn" onClick={addReading}>
                + Add Reading
              </button>
            </div>
            {readings.map((reading, idx) => (
              <ReadingEditor
                key={idx}
                index={idx}
                value={reading}
                onChange={(data) => updateReading(idx, data)}
                onRemove={() => removeReading(idx)}
                defaultDecks={defaults?.default_decks}
              />
            ))}
            {readings.length === 0 && (
              <div className="entry-editor__empty">
                No readings added yet. Click "+ Add Reading" to record a card reading.
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="entry-editor__section">
            <h3 className="entry-editor__section-title">Notes</h3>
            <RichTextEditor
              content={content}
              onChange={setContent}
              placeholder="Write your thoughts, interpretations, reflections..."
              minHeight={150}
            />
          </div>

          {/* Tags */}
          {allTags.length > 0 && (
            <div className="entry-editor__section">
              <h3 className="entry-editor__section-title">Tags</h3>
              <div className="entry-editor__tags">
                {allTags.map((tag) => (
                  <label key={tag.id} className="entry-editor__tag-check">
                    <input
                      type="checkbox"
                      checked={selectedTagIds.includes(tag.id)}
                      onChange={() => toggleTag(tag.id)}
                    />
                    <span
                      className="entry-editor__tag-badge"
                      style={{ backgroundColor: tag.color }}
                    >
                      {tag.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="entry-editor__footer">
          {error && <div className="entry-editor__error">{error}</div>}
          <div className="entry-editor__footer-buttons">
            <button onClick={onClose}>Cancel</button>
            <button className="primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Entry'}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
