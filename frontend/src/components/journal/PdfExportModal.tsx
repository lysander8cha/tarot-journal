import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  exportEntryPdf,
  getExportOptions,
  type ArchetypeFieldOption,
} from '../../api/pdfExport';
import { useToast } from '../../context/ToastContext';
import Modal, { ModalCancelButton } from '../common/Modal';
import { useEntryBreakdown } from '../../utils/readingBreakdown';
import { CORRESPONDENCE_FIELD_LABELS } from '../../types';
import type { JournalEntryFull, BreakdownSettings, Spread } from '../../types';
import { getSpreads } from '../../api/spreads';
import { loadSuitViewMode, type SuitViewMode } from '../../utils/suitPairing';
import { useQuerentBirthCards } from './QuerentBirthCards';
import './PdfExportModal.css';

interface Props {
  entry: JournalEntryFull;
  open: boolean;
  onClose: () => void;
}

/**
 * Default sub-toggles for the Correspondence Breakdown section.
 * Prefer the visibility the user already saved for this entry's
 * in-app Reading Breakdown; otherwise enable every present field.
 */
function defaultEnabledFields(
  presentFilterFields: string[],
  savedSettings: BreakdownSettings | null,
): Set<string> {
  if (!savedSettings) {
    return new Set(presentFilterFields);
  }
  const visible = savedSettings.visible || {};
  return new Set(
    presentFilterFields.filter(f => visible[f] !== false),
  );
}

function parseBreakdownSettings(raw: string | null): BreakdownSettings | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return {
      open: typeof parsed.open === 'boolean' ? parsed.open : false,
      last_tab:
        parsed.last_tab === 'all' || typeof parsed.last_tab === 'number'
          ? parsed.last_tab
          : 'all',
      visible:
        parsed.visible && typeof parsed.visible === 'object'
          ? parsed.visible
          : {},
    };
  } catch {
    return null;
  }
}

function labelForField(field: string): string {
  if (field === 'suit') return 'Suit';
  if (field === 'rank') return 'Rank';
  return CORRESPONDENCE_FIELD_LABELS[field] || field;
}

/**
 * Phase 3 of the journal PDF export modal. Reading selection,
 * the correspondence breakdown master + sub-toggles, AND the new
 * card-custom-fields and archetype-reference master toggles with
 * their own sub-checklists. The astrological event chart toggle
 * remains stubbed for phase 4.
 */
export default function PdfExportModal({ entry, open, onClose }: Props) {
  const { showToast } = useToast();
  const [selectedReadings, setSelectedReadings] = useState<Set<number>>(
    new Set(),
  );
  const [generating, setGenerating] = useState(false);

  // Correspondence breakdown state (phase 2).
  const [includeCorrespondences, setIncludeCorrespondences] = useState(false);
  // Defaults to the app-wide suit display preference (Insights /
  // Reading Breakdown share it via localStorage).
  const [suitView, setSuitView] = useState<SuitViewMode>(loadSuitViewMode);
  const [enabledFields, setEnabledFields] = useState<Set<string>>(new Set());

  // Phase 3 state.
  const [includeCustomFields, setIncludeCustomFields] = useState(false);
  const [enabledCustomFields, setEnabledCustomFields] = useState<Set<string>>(
    new Set(),
  );
  const [includeArchetypeFields, setIncludeArchetypeFields] = useState(false);
  const [enabledArchetypeFieldIds, setEnabledArchetypeFieldIds] =
    useState<Set<number>>(new Set());

  // Phase 4 — astrological event chart.
  const [includeChart, setIncludeChart] = useState(false);

  // Spread instructions under each reading's layout.
  const [includeSpreadInstructions, setIncludeSpreadInstructions] = useState(false);
  const [markBirthCards, setMarkBirthCards] = useState(false);
  const [markNameCards, setMarkNameCards] = useState(false);

  // The querents' Greer birth/name cards, same source as the entry
  // viewer's "Indicate Birth & Name Cards" (cached, so no refetch).
  const birthCards = useQuerentBirthCards(
    entry.querents,
    entry.reading_datetime ? new Date(entry.reading_datetime).getFullYear() : undefined,
    open,
  );
  const hasTarotReading = entry.readings.some(r =>
    r.cartomancy_type === 'Tarot'
    || (r.cards_used || []).some(c => c.cartomancy_type === 'Tarot'));
  const birthMarksAvailable = hasTarotReading && birthCards.labelsBySystem.birth.size > 0;
  const nameMarksAvailable = hasTarotReading && birthCards.labelsBySystem.name.size > 0;
  const { data: allSpreads = [] } = useQuery<Spread[]>({
    queryKey: ['spreads'],
    queryFn: getSpreads,
    enabled: open,
  });
  // Only offer the toggle when a selected reading's spread actually
  // has instructions to print.
  const spreadInstructionsAvailable = useMemo(() => {
    if (!entry) return false;
    const spreadIds = new Set(
      entry.readings.filter(r => r.spread_id != null).map(r => r.spread_id));
    return allSpreads.some(s =>
      spreadIds.has(s.id)
      && (s.description || '').replace(/<[^>]*>/g, '').trim().length > 0);
  }, [entry, allSpreads]);

  const breakdown = useEntryBreakdown(open ? entry : undefined);
  const presentFilterFields = breakdown.presentFilterFields;
  const savedSettings = useMemo(
    () => parseBreakdownSettings(entry.breakdown_settings),
    [entry.breakdown_settings],
  );

  // Reset selection whenever the modal opens or the entry changes,
  // defaulting to "all readings" and (per the planning doc) the
  // user's saved breakdown visibility for the sub-toggles.
  useEffect(() => {
    if (open) {
      setSelectedReadings(new Set(entry.readings.map(r => r.id)));
      setIncludeCorrespondences(false);
      setIncludeCustomFields(false);
      setIncludeArchetypeFields(false);
      setIncludeChart(false);
    }
  }, [open, entry.id, entry.readings]);

  // Re-seed breakdown sub-toggles once the breakdown data resolves
  // (queries fan out per card so it can take a render or two).
  useEffect(() => {
    if (!open) return;
    if (presentFilterFields.length === 0) return;
    setEnabledFields(defaultEnabledFields(presentFilterFields, savedSettings));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, entry.id, presentFilterFields.join('|')]);

  // Fetch available custom + archetype fields whenever the reading
  // selection changes — the server scopes both lists to whatever
  // readings are currently in. Reuses the export-options endpoint.
  const readingsKey = useMemo(
    () => [...selectedReadings].sort((a, b) => a - b),
    [selectedReadings],
  );
  const { data: discovery, isLoading: optionsLoading } = useQuery({
    queryKey: ['pdf-export-options', entry.id, readingsKey],
    queryFn: () => getExportOptions(entry.id, readingsKey),
    enabled: open && readingsKey.length > 0,
  });

  // Default sub-toggles to "all present" each time the discovery
  // response changes — per the planning doc.
  useEffect(() => {
    if (!discovery) return;
    setEnabledCustomFields(new Set(discovery.custom_fields));
    setEnabledArchetypeFieldIds(
      new Set(discovery.archetype_fields.map(f => f.field_id)),
    );
  }, [discovery]);

  const hasMultipleReadings = entry.readings.length > 1;
  const noneSelected = selectedReadings.size === 0;
  const hasFilterableBreakdown = presentFilterFields.length > 0;
  const customFieldsAvailable = (discovery?.custom_fields.length ?? 0) > 0;
  const archetypeFieldsAvailable = (discovery?.archetype_fields.length ?? 0) > 0;
  const chartAvailable = discovery?.chart_available ?? false;

  // The disabled-state hint distinguishes "missing date/time" from
  // "missing location" so the user knows what to fill in. Mirrors
  // the gating the entry/<id>/chart route applies.
  const chartHint = useMemo(() => {
    if (optionsLoading) return 'Checking event chart data…';
    if (chartAvailable) return null;
    const missing: string[] = [];
    if (!entry.reading_datetime) missing.push('date/time');
    if (entry.location_lat == null || entry.location_lon == null) {
      missing.push('location');
    }
    if (missing.length === 0) {
      return 'Event chart unavailable for this entry.';
    }
    return `Add ${missing.join(' and ')} to this entry to enable the event chart.`;
  }, [optionsLoading, chartAvailable, entry.reading_datetime, entry.location_lat, entry.location_lon]);

  const orderedReadings = useMemo(
    () => [...entry.readings].sort((a, b) => a.id - b.id),
    [entry.readings],
  );

  // Group archetype fields by source so the checklist shows
  // "Pollack — Upright Meaning" style rows under each source header.
  const archetypeFieldsBySource = useMemo(() => {
    if (!discovery) return [];
    const grouped = new Map<number, { source_name: string; fields: ArchetypeFieldOption[] }>();
    for (const f of discovery.archetype_fields) {
      let bucket = grouped.get(f.source_id);
      if (!bucket) {
        bucket = { source_name: f.source_name, fields: [] };
        grouped.set(f.source_id, bucket);
      }
      bucket.fields.push(f);
    }
    return [...grouped.values()];
  }, [discovery]);

  const toggleReading = (id: number) => {
    setSelectedReadings(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleField = (field: string) => {
    setEnabledFields(prev => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  };

  const toggleCustomField = (name: string) => {
    setEnabledCustomFields(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleArchetypeField = (id: number) => {
    setEnabledArchetypeFieldIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  /** The chosen systems' labels merged into one archetype → mark map. */
  const cardMarks = () => {
    const marks: Record<string, { label: string; colors: string[] }> = {};
    const add = (map: Map<string, { label: string; colors: string[] }>) => {
      for (const [key, tag] of map) {
        const prior = marks[key];
        marks[key] = prior
          ? { label: `${prior.label} · ${tag.label}`,
              colors: [...new Set([...prior.colors, ...tag.colors])] }
          : { label: tag.label, colors: [...tag.colors] };
      }
    };
    if (markBirthCards && birthMarksAvailable) add(birthCards.labelsBySystem.birth);
    if (markNameCards && nameMarksAvailable) add(birthCards.labelsBySystem.name);
    return Object.keys(marks).length ? marks : undefined;
  };

  const handleGenerate = async () => {
    if (noneSelected) return;
    setGenerating(true);
    try {
      await exportEntryPdf(entry.id, {
        readings: [...selectedReadings],
        include_correspondences: includeCorrespondences && hasFilterableBreakdown,
        suit_view: suitView,
        correspondence_types:
          includeCorrespondences && hasFilterableBreakdown
            ? [...enabledFields]
            : undefined,
        include_custom_fields: includeCustomFields && customFieldsAvailable,
        custom_fields:
          includeCustomFields && customFieldsAvailable
            ? [...enabledCustomFields]
            : undefined,
        include_archetype_fields:
          includeArchetypeFields && archetypeFieldsAvailable,
        archetype_fields:
          includeArchetypeFields && archetypeFieldsAvailable
            ? [...enabledArchetypeFieldIds]
            : undefined,
        include_chart: includeChart && chartAvailable,
        include_spread_instructions:
          includeSpreadInstructions && spreadInstructionsAvailable,
        card_marks: cardMarks(),
      });
      showToast('PDF downloaded');
      onClose();
    } catch (e) {
      console.error('PDF export failed:', e);
      showToast('PDF export failed — see console for details');
    } finally {
      setGenerating(false);
    }
  };

  if (!open) return null;

  return (
    <Modal open={true} onClose={onClose} title="Export to PDF" width={520}>
      <div className="pdf-export-modal__body">
          {hasMultipleReadings && (
            <section className="pdf-export-modal__section">
              <h3>Readings to include</h3>
              <ul className="pdf-export-modal__list">
                {orderedReadings.map(r => (
                  <li key={r.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={selectedReadings.has(r.id)}
                        onChange={() => toggleReading(r.id)}
                      />
                      <span>
                        {r.spread_name || `Reading ${r.id}`}
                        {r.deck_name ? ` — ${r.deck_name}` : ''}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              {noneSelected && (
                <p className="pdf-export-modal__error">
                  Select at least one reading to include.
                </p>
              )}
            </section>
          )}

          <section className="pdf-export-modal__section">
            <h3>Always included</h3>
            <ul className="pdf-export-modal__static-list">
              <li>Header (title, date, location, querents/reader, tags)</li>
              <li>Spread layout with card images and position labels</li>
              <li>Position key (position → card name)</li>
              <li>Journal entry notes</li>
              <li>Follow-up notes</li>
            </ul>
          </section>

          <section className="pdf-export-modal__section">
            <h3>Correspondence breakdown</h3>
            <label className="pdf-export-modal__master">
              <input
                type="checkbox"
                checked={includeCorrespondences}
                onChange={e => setIncludeCorrespondences(e.target.checked)}
                disabled={!hasFilterableBreakdown}
              />
              <span>Include correspondence breakdown</span>
            </label>
            {!hasFilterableBreakdown && (
              <p className="pdf-export-modal__hint">
                {breakdown.isLoading
                  ? 'Loading card correspondences…'
                  : 'No correspondences resolved for this entry — nothing to break down.'}
              </p>
            )}
            {includeCorrespondences && hasFilterableBreakdown && enabledFields.has('suit') && (
              <label className="pdf-export-modal__suit-view">
                Suit display
                <select
                  value={suitView}
                  onChange={e => setSuitView(e.target.value as SuitViewMode)}
                >
                  <option value="separate">Separate (Cups, Hearts, …)</option>
                  <option value="paired">Paired (Cups / Hearts, …)</option>
                </select>
              </label>
            )}
            {includeCorrespondences && hasFilterableBreakdown && (
              <ul className="pdf-export-modal__list pdf-export-modal__list--nested">
                {presentFilterFields.map(field => (
                  <li key={field}>
                    <label>
                      <input
                        type="checkbox"
                        checked={enabledFields.has(field)}
                        onChange={() => toggleField(field)}
                      />
                      <span>{labelForField(field)}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="pdf-export-modal__section">
            <h3>Card custom fields</h3>
            <label className="pdf-export-modal__master">
              <input
                type="checkbox"
                checked={includeCustomFields}
                onChange={e => setIncludeCustomFields(e.target.checked)}
                disabled={!customFieldsAvailable}
              />
              <span>Include card custom fields</span>
            </label>
            {!customFieldsAvailable && (
              <p className="pdf-export-modal__hint">
                {optionsLoading
                  ? 'Loading available fields…'
                  : 'No custom fields are populated on the cards in this entry.'}
              </p>
            )}
            {includeCustomFields && customFieldsAvailable && (
              <ul className="pdf-export-modal__list pdf-export-modal__list--nested">
                {discovery!.custom_fields.map(name => (
                  <li key={name}>
                    <label>
                      <input
                        type="checkbox"
                        checked={enabledCustomFields.has(name)}
                        onChange={() => toggleCustomField(name)}
                      />
                      <span>{name}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="pdf-export-modal__section">
            <h3>Archetype reference info</h3>
            <label className="pdf-export-modal__master">
              <input
                type="checkbox"
                checked={includeArchetypeFields}
                onChange={e => setIncludeArchetypeFields(e.target.checked)}
                disabled={!archetypeFieldsAvailable}
              />
              <span>Include archetype reference info</span>
            </label>
            {!archetypeFieldsAvailable && (
              <p className="pdf-export-modal__hint">
                {optionsLoading
                  ? 'Loading available fields…'
                  : 'No archetype reference entries authored for the cards in this entry.'}
              </p>
            )}
            {includeArchetypeFields && archetypeFieldsAvailable && (
              <div className="pdf-export-modal__nested-groups">
                {archetypeFieldsBySource.map(group => (
                  <div key={group.source_name} className="pdf-export-modal__nested-group">
                    <div className="pdf-export-modal__nested-group-title">
                      {group.source_name}
                    </div>
                    <ul className="pdf-export-modal__list pdf-export-modal__list--nested">
                      {group.fields.map(f => (
                        <li key={f.field_id}>
                          <label>
                            <input
                              type="checkbox"
                              checked={enabledArchetypeFieldIds.has(f.field_id)}
                              onChange={() => toggleArchetypeField(f.field_id)}
                            />
                            <span>{f.field_name}</span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="pdf-export-modal__section">
            <h3>Spread instructions</h3>
            <label className="pdf-export-modal__master">
              <input
                type="checkbox"
                checked={includeSpreadInstructions && spreadInstructionsAvailable}
                onChange={e => setIncludeSpreadInstructions(e.target.checked)}
                disabled={!spreadInstructionsAvailable}
              />
              <span>Include each spread's description &amp; instructions</span>
            </label>
            {!spreadInstructionsAvailable && (
              <p className="pdf-export-modal__hint">
                None of this entry's spreads have a description.
              </p>
            )}
          </section>

          {(birthMarksAvailable || nameMarksAvailable) && (
            <section className="pdf-export-modal__section">
              <h3>Birth &amp; name cards</h3>
              {birthMarksAvailable && (
                <label className="pdf-export-modal__master">
                  <input
                    type="checkbox"
                    checked={markBirthCards}
                    onChange={e => setMarkBirthCards(e.target.checked)}
                  />
                  <span>Mark the querents' birth cards</span>
                </label>
              )}
              {nameMarksAvailable && (
                <label className="pdf-export-modal__master">
                  <input
                    type="checkbox"
                    checked={markNameCards}
                    onChange={e => setMarkNameCards(e.target.checked)}
                  />
                  <span>Mark the querents' name cards</span>
                </label>
              )}
              <p className="pdf-export-modal__hint">
                Marked Tarot cards get a colored frame and their role (Soul, Theme Note…).
              </p>
            </section>
          )}

          <section className="pdf-export-modal__section">
            <h3>Astrological event chart</h3>
            <label className="pdf-export-modal__master">
              <input
                type="checkbox"
                checked={includeChart && chartAvailable}
                onChange={e => setIncludeChart(e.target.checked)}
                disabled={!chartAvailable}
              />
              <span>Include event chart</span>
            </label>
            {chartHint && (
              <p className="pdf-export-modal__hint">{chartHint}</p>
            )}
          </section>
        </div>

      <div className="pdf-export-modal__footer">
        <ModalCancelButton className="pdf-export-modal__cancel" disabled={generating}>
          Cancel
        </ModalCancelButton>
        <button
          type="button"
          className="pdf-export-modal__generate"
          onClick={handleGenerate}
          disabled={noneSelected || generating}
        >
          {generating ? 'Generating…' : 'Generate PDF'}
        </button>
      </div>
    </Modal>
  );
}
