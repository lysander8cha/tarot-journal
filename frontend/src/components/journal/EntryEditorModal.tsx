import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getEntry,
  createEntry,
  updateEntry,
  replaceEntryReadings,
  setEntryTags,
  setEntryQuerents,
  getProfiles,
  getRecentLocations,
  type RecentLocation,
} from '../../api/entries';
import { getEntryTags as getAllEntryTags } from '../../api/tags';
import { getDefaults, type AppDefaults } from '../../api/settings';
import { useToast } from '../../context/ToastContext';
import Modal, { ModalCancelButton } from '../common/Modal';
import RichTextEditor from '../common/RichTextEditor';
import ReadingEditor, { type ReadingData } from './ReadingEditor';
import type { JournalEntryFull, Tag, Profile } from '../../types';
import PlaceLookupButton from '../common/PlaceLookupButton';
import './EntryEditorModal.css';

interface InitialFormState {
  title: string;
  readingDatetime: string;
  locationName: string;
  locationLat: number | null;
  locationLon: number | null;
  querentIds: number[];
  readerId: number | null;
  content: string;
  readings: ReadingData[];
  selectedTagIds: number[];
}

interface EntryEditorModalProps {
  entryId: number | null; // null = creating new entry
  /** When creating (entryId null): copy this entry's structure —
   *  spreads, decks, querents, reader, tags, title — with empty card
   *  slots and today's date. The daily-draw "same again" workflow. */
  templateEntryId?: number | null;
  open: boolean;
  onClose: () => void;
  onSaved: (entryId: number) => void;
}

function emptyReading(): ReadingData {
  return {
    _key: crypto.randomUUID(),
    spread_id: null,
    spread_name: null,
    deck_id: null,
    deck_name: null,
    cartomancy_type: null,
    notes: '',
    cards: [],
  };
}

function nowLocalISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Convert a stored reading_datetime to the naive-local YYYY-MM-DDTHH:MM
 * format the <input type="datetime-local"> control expects.
 *
 * Older entries (and any saved through earlier builds of the "Now"
 * button) recorded UTC ISO strings with a trailing `Z` or an explicit
 * `+HH:MM` offset. Slicing those directly drops the offset and shifts
 * the wall-clock by the user's TZ, which is the bug we're fixing.
 * Detect any timezone marker, parse via `new Date()` (which respects
 * it), then re-emit using the local clock.
 *
 * Values without a timezone marker are already naive local — pass
 * them through after trimming to minute precision.
 */
function storedToLocalInput(stored: string): string {
  const trimmed = stored.replace(' ', 'T');
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(trimmed);
  if (hasTimezone) {
    const d = new Date(trimmed);
    if (!Number.isNaN(d.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
  }
  return trimmed.slice(0, 16);
}

export default function EntryEditorModal({ entryId, templateEntryId, open, onClose, onSaved }: EntryEditorModalProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const isEditing = entryId !== null;
  const useTemplate = !isEditing && templateEntryId != null;

  // Load existing entry if editing
  const { data: existingEntry } = useQuery<JournalEntryFull>({
    queryKey: ['entry', entryId],
    queryFn: () => getEntry(entryId!),
    enabled: isEditing && open,
  });

  // Load the entry whose structure a new entry should copy
  const { data: templateEntry } = useQuery<JournalEntryFull>({
    queryKey: ['entry', templateEntryId],
    queryFn: () => getEntry(templateEntryId!),
    enabled: useTemplate && open,
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

  const { data: recentLocations = [] } = useQuery<RecentLocation[]>({
    queryKey: ['recent-locations'],
    queryFn: getRecentLocations,
    enabled: open,
  });

  // Form state
  const [title, setTitle] = useState('');
  // Pre-filled with the moment the editor opened (the closest thing
  // to when the reading happened); always visible and editable, with
  // a "Now" button to re-stamp. Never silently changes on save.
  const [readingDatetime, setReadingDatetime] = useState(nowLocalISO());
  const [locationName, setLocationName] = useState('');
  const [locationLat, setLocationLat] = useState<number | null>(null);
  const [locationLon, setLocationLon] = useState<number | null>(null);
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
      const datetimeVal = existingEntry.reading_datetime
        ? storedToLocalInput(existingEntry.reading_datetime)
        : nowLocalISO();
      const locationVal = existingEntry.location_name || '';
      const locationLatVal = existingEntry.location_lat ?? null;
      const locationLonVal = existingEntry.location_lon ?? null;
      // Use querents array, or fall back to legacy querent_id if empty
      const querentIdsVal = existingEntry.querents?.length
        ? existingEntry.querents.map(q => q.id)
        : (existingEntry.querent_id ? [existingEntry.querent_id] : []);
      const readerVal = existingEntry.reader_id;
      const contentVal = existingEntry.content || '';
      const tagIds = existingEntry.tags.map(t => t.id);

      // Convert existing readings to ReadingData
      const readingData: ReadingData[] = existingEntry.readings.map(r => ({
        _key: crypto.randomUUID(),
        spread_id: r.spread_id,
        spread_name: r.spread_name,
        deck_id: r.deck_id,
        deck_name: r.deck_name,
        cartomancy_type: r.cartomancy_type,
        notes: r.notes ?? '',
        cards: (r.cards_used || []).map((c, idx) => ({
          name: c.name,
          reversed: c.reversed || false,
          deck_id: c.deck_id,
          deck_name: c.deck_name,
          position_index: c.position_index ?? idx,
          card_id: c.card_id,  // Preserve card_id for reliable lookup
          clarifies: c.clarifies,
        })),
      }));

      setTitle(titleVal);
      setReadingDatetime(datetimeVal);
      setLocationName(locationVal);
      setLocationLat(locationLatVal);
      setLocationLon(locationLonVal);
      setQuerentIds(querentIdsVal);
      setReaderId(readerVal);
      setContent(contentVal);
      setSelectedTagIds(tagIds);
      setReadings(readingData.length > 0 ? readingData : []);

      // Store initial state for dirty checking
      initialStateRef.current = {
        title: titleVal,
        readingDatetime: datetimeVal,
        locationName: locationVal,
        locationLat: locationLatVal,
        locationLon: locationLonVal,
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
      // Template mode: wait for the template entry to load, then
      // prefill its structure (handled below) instead of blank+defaults.
      if (useTemplate && !templateEntry) return;

      const datetimeVal = nowLocalISO();
      // Apply defaults for reader and querent
      const defaultReader = defaults?.default_reader ?? null;
      const defaultQuerent = defaults?.default_querent_same_as_reader
        ? defaultReader
        : (defaults?.default_querent ?? null);
      const defaultQuerentIds = defaultQuerent ? [defaultQuerent] : [];

      let titleVal = '';
      let querentIdsVal = defaultQuerentIds;
      let readerVal = defaultReader;
      let tagIdsVal: number[] = [];
      // A fresh entry starts with one open reading slot — logging a
      // reading is why the editor was opened, so don't make the user
      // click "+ Add Reading" first.
      let readingsVal: ReadingData[] = [emptyReading()];

      if (useTemplate && templateEntry) {
        titleVal = templateEntry.title || '';
        querentIdsVal = templateEntry.querents?.length
          ? templateEntry.querents.map(q => q.id)
          : (templateEntry.querent_id ? [templateEntry.querent_id] : []);
        readerVal = templateEntry.reader_id;
        tagIdsVal = templateEntry.tags.map(t => t.id);
        // Same spreads and decks, but every card slot empty. Deck ids
        // stay on the empty cards so multi-deck slot assignments carry
        // over (the reading editor derives slot decks from them).
        readingsVal = templateEntry.readings.map(r => ({
          _key: crypto.randomUUID(),
          spread_id: r.spread_id,
          spread_name: r.spread_name,
          deck_id: r.deck_id,
          deck_name: r.deck_name,
          cartomancy_type: r.cartomancy_type,
          notes: '',
          cards: (r.cards_used || []).map((c, idx) => ({
            name: '',
            reversed: false,
            deck_id: c.deck_id,
            deck_name: c.deck_name,
            position_index: c.position_index ?? idx,
          })),
        }));
      }

      setTitle(titleVal);
      setReadingDatetime(datetimeVal);
      setLocationName('');
      setLocationLat(null);
      setLocationLon(null);
      setReaderId(readerVal);
      setQuerentIds(querentIdsVal);
      setContent('');
      setReadings(readingsVal);
      setSelectedTagIds(tagIdsVal);
      setInitialized(false);
      setError(null);

      // Store initial state for dirty checking
      initialStateRef.current = {
        title: titleVal,
        readingDatetime: datetimeVal,
        locationName: '',
        locationLat: null,
        locationLon: null,
        querentIds: querentIdsVal,
        readerId: readerVal,
        content: '',
        readings: readingsVal,
        selectedTagIds: tagIdsVal,
      };
    }
    if (open && isEditing) {
      setInitialized(false);
      setError(null);
    }
  }, [open, entryId, defaults, useTemplate, templateEntry]);

  const toggleTag = (tagId: number) => {
    setSelectedTagIds(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
  };

  const addReading = () => {
    setReadings(prev => [...prev, emptyReading()]);
  };

  // "Add reading like this": a fresh reading with the previous one's
  // spread and deck setup — card slots empty, but keeping each slot's
  // deck assignment so multi-deck spreads carry their slot mapping.
  const addReadingLikeLast = () => {
    setReadings(prev => {
      const last = prev[prev.length - 1];
      if (!last) return [...prev, emptyReading()];
      return [...prev, {
        _key: crypto.randomUUID(),
        spread_id: last.spread_id,
        spread_name: last.spread_name,
        deck_id: last.deck_id,
        deck_name: last.deck_name,
        cartomancy_type: last.cartomancy_type,
        notes: '',
        cards: last.cards.map(c => ({
          name: '',
          reversed: false,
          deck_id: c.deck_id,
          deck_name: c.deck_name,
          position_index: c.position_index,
        })),
      }];
    });
  };

  const updateReading = (idx: number, data: ReadingData) => {
    setReadings(prev => prev.map((r, i) => (i === idx ? data : r)));
  };

  const removeReading = (idx: number) => {
    setReadings(prev => prev.filter((_, i) => i !== idx));
  };

  // Swap a reading with its neighbor. Saved position_order follows
  // array order, so the new arrangement persists on save.
  const moveReading = (idx: number, direction: -1 | 1) => {
    setReadings(prev => {
      const target = idx + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const datetime = readingDatetime;
      // Filter out any unselected querents (value 0)
      const validQuerentIds = querentIds.filter(id => id > 0);

      const entryData = {
        title: title.trim() || undefined,
        content: content || undefined,
        reading_datetime: datetime || undefined,
        location_name: locationName.trim() || undefined,
        location_lat: locationLat,
        location_lon: locationLon,
        // Legacy querent_id: first querent or null
        querent_id: validQuerentIds.length > 0 ? validQuerentIds[0] : null,
        reader_id: readerId,
      };

      let savedEntryId: number;

      if (isEditing) {
        await updateEntry(entryId!, entryData);
        savedEntryId = entryId!;
      } else {
        const result = await createEntry(entryData);
        savedEntryId = result.id;
      }

      // Save all readings in one atomic request. The backend swaps the
      // old readings for the new set inside a single transaction, so a
      // failure here leaves the entry's original readings intact —
      // unlike the old delete-then-re-add flow, which could destroy
      // them if a save failed partway.
      let readingsFailed = false;
      // Skip completely untouched reading slots (no spread, no deck,
      // no cards) — new entries open with one ready to fill, and an
      // unused slot shouldn't save an empty reading.
      const meaningfulReadings = readings.filter(
        r => r.spread_id || r.deck_id || r.cards.some(c => c.name.trim()),
      );
      try {
        await replaceEntryReadings(savedEntryId, meaningfulReadings.map((r, i) => ({
          spread_id: r.spread_id,
          spread_name: r.spread_name || undefined,
          notes: (r.notes || '').replace(/<[^>]*>/g, '').trim() ? r.notes : undefined,
          deck_id: r.deck_id,
          deck_name: r.deck_name || undefined,
          cartomancy_type: r.cartomancy_type || undefined,
          cards_used: r.cards
            .filter(c => c.name.trim())
            .map(c => ({
              name: c.name,
              reversed: c.reversed,
              deck_id: c.deck_id,
              deck_name: c.deck_name,
              position_index: c.position_index,
              card_id: c.card_id,  // Store card_id so entries survive card renames
              clarifies: c.clarifies,
            })),
          position_order: i,
        })));
      } catch (readingErr) {
        console.error('Failed to save readings:', readingErr);
        readingsFailed = true;
      }

      // Set tags
      let tagsFailed = false;
      try {
        await setEntryTags(savedEntryId, selectedTagIds);
      } catch (tagErr) {
        console.error('Failed to save tags:', tagErr);
        tagsFailed = true;
      }

      // Set querents
      let querentsFailed = false;
      try {
        await setEntryQuerents(savedEntryId, validQuerentIds);
      } catch (querentErr) {
        console.error('Failed to save querents:', querentErr);
        querentsFailed = true;
      }

      // Report any partial failures
      const failures: string[] = [];
      if (readingsFailed) {
        failures.push(isEditing
          ? 'readings (your previous readings are unchanged)'
          : 'readings');
      }
      if (tagsFailed) {
        failures.push('tags');
      }
      if (querentsFailed) {
        failures.push('querents');
      }

      if (failures.length > 0) {
        showToast(`Entry saved, but failed to save: ${failures.join(', ')}.`, 'warning');
        // Still close and notify - the entry was saved
        queryClient.invalidateQueries({ queryKey: ['entries'] });
        queryClient.invalidateQueries({ queryKey: ['entry-search'] });
        queryClient.invalidateQueries({ queryKey: ['entry', savedEntryId] });
        onSaved(savedEntryId);
        // Don't close - let user see the warning
        setSaving(false);
        return;
      }

      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ['entries'] });
      queryClient.invalidateQueries({ queryKey: ['entry-search'] });
      queryClient.invalidateQueries({ queryKey: ['entry', savedEntryId] });

      onSaved(savedEntryId);
      onClose();
    } catch (err) {
      console.error('Failed to save entry:', err);
      showToast('Failed to save entry.');
    } finally {
      setSaving(false);
    }
  };

  // Cmd+Enter (Ctrl+Enter) saves — lets a keyboard-driven entry go
  // from Cmd+N to saved without touching the mouse. Re-registered
  // every render so the handler always sees current state.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (!saving) handleSave();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Compute whether form has unsaved changes
  const isDirty = useMemo(() => {
    const initial = initialStateRef.current;
    if (!initial) return false;

    // Compare simple fields
    if (title !== initial.title) return true;
    if (readingDatetime !== initial.readingDatetime) return true;
    if (locationName !== initial.locationName) return true;
    if (locationLat !== initial.locationLat) return true;
    if (locationLon !== initial.locationLon) return true;
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
  }, [title, readingDatetime, locationName, locationLat, locationLon, querentIds, readerId, content, selectedTagIds, readings]);

  if (!open) return null;

  return (
    <Modal open={true} onClose={onClose} width={800} isDirty={isDirty}>
      <div className="entry-editor">
        <div className="tj-kicker entry-editor__kicker">
          {isEditing ? 'Edit entry' : 'New entry · draft'}
        </div>

        <div className="entry-editor__form">
          {/* Title — a borderless serif input; the entry IS the title */}
          <input
            type="text"
            className="entry-editor__title-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Untitled entry"
          />

          {/* Date/Time */}
          <div className="entry-editor__field">
            <label className="entry-editor__label">Date &amp; Time</label>
            <div className="entry-editor__date-row">
              <input
                type="datetime-local"
                value={readingDatetime}
                onChange={(e) => setReadingDatetime(e.target.value)}
                className="entry-editor__datetime-input"
              />
              <button
                type="button"
                className="entry-editor__now-btn"
                onClick={() => setReadingDatetime(nowLocalISO())}
                title="Set to the current time"
              >
                Now
              </button>
            </div>
          </div>

          {/* Location */}
          <div className="entry-editor__field">
            <label className="entry-editor__label">Location</label>
            <div className="entry-editor__place-row">
              <input
                type="text"
                value={locationName}
                onChange={(e) => {
                  setLocationName(e.target.value);
                  // Clear stale coords when name changes.
                  setLocationLat(null);
                  setLocationLon(null);
                }}
                placeholder="Where the reading took place (optional)"
              />
              <PlaceLookupButton
                query={locationName}
                onSelect={(m) => {
                  setLocationName(m.display_name);
                  setLocationLat(m.latitude);
                  setLocationLon(m.longitude);
                }}
              />
            </div>
            {locationLat != null && locationLon != null && (
              <div className="entry-editor__place-coords">
                {locationLat.toFixed(3)}, {locationLon.toFixed(3)}
              </div>
            )}
            {/* One-tap recent locations, shown while the field is
                empty; picking one reuses its saved coordinates. */}
            {locationName.trim() === '' && recentLocations.length > 0 && (
              <div className="entry-editor__recent-locations">
                {recentLocations.slice(0, 5).map((loc) => (
                  <button
                    key={loc.location_name}
                    type="button"
                    className="entry-editor__recent-location-chip"
                    title={loc.location_name}
                    onClick={() => {
                      setLocationName(loc.location_name);
                      setLocationLat(loc.location_lat);
                      setLocationLon(loc.location_lon);
                    }}
                  >
                    {loc.location_name}
                  </button>
                ))}
              </div>
            )}
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
                          {profiles
                            .filter((p) => !p.hidden || p.id === qId)
                            .map((p) => (
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
                <div className="entry-editor__querents-header">
                  <label className="entry-editor__label">Reader</label>
                </div>
                <select
                  value={readerId ?? ''}
                  onChange={(e) => setReaderId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">None</option>
                  {profiles
                    .filter((p) => !p.querent_only && (!p.hidden || p.id === readerId))
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
            </div>
            {readings.map((reading, idx) => (
              <ReadingEditor
                key={reading._key ?? `reading-${idx}`}
                index={idx}
                value={reading}
                showNotes={readings.length > 1
                  || !!(reading.notes || '').replace(/<[^>]*>/g, '').trim()}
                onChange={(data) => updateReading(idx, data)}
                onRemove={() => removeReading(idx)}
                defaultDecks={defaults?.default_decks}
                onMoveUp={idx > 0 ? () => moveReading(idx, -1) : undefined}
                onMoveDown={idx < readings.length - 1 ? () => moveReading(idx, 1) : undefined}
              />
            ))}
            {readings.length === 0 && (
              <div className="entry-editor__empty">
                No readings added yet. Click "+ Add Reading" to record a card reading.
              </div>
            )}
            {/* Below the readings so adding the next one doesn't mean
                scrolling back past everything already entered. */}
            <button className="entry-editor__add-btn" onClick={addReading}>
              + Add Reading
            </button>
            {readings.length > 0
              && (readings[readings.length - 1].spread_id != null
                || readings[readings.length - 1].deck_id != null) && (
              <button
                className="entry-editor__add-btn"
                onClick={addReadingLikeLast}
                title="New reading with the previous reading's spread and deck, cards empty"
              >
                + Add Reading Like This
              </button>
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
            <ModalCancelButton>Cancel</ModalCancelButton>
            <button className="primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Entry'}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
