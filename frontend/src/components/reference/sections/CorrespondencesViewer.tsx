import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getArchetypes,
  getCorrespondenceSystems,
  getCorrespondenceSystem,
  compareCorrespondenceSystems,
  type Archetype,
} from '../../../api/correspondences';
import { getBulkGroups } from '../../../utils/bulkGroups';
import type { CorrespondenceSystem, CorrespondenceAssignment } from '../../../types';
import { CORRESPONDENCE_FIELDS, CORRESPONDENCE_FIELD_LABELS } from '../../../types';
import { detectGroupPatterns, patternsByCategory, type PatternCategorySection } from '../../../utils/correspondencePatterns';
import { displayArchetypeName, displayGroupLabel } from '../../../utils/tarotNaming';
import './CorrespondencesViewer.css';

type ViewMode = 'by-system' | 'compare';

interface CorrespondencesViewerProps {
  onEditCorrespondences?: (section: string) => void;
}

export default function CorrespondencesViewer({ onEditCorrespondences }: CorrespondencesViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('by-system');
  const [selectedSystemId, setSelectedSystemId] = useState<number | null>(null);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [filterText, setFilterText] = useState('');
  const [typeFilter, setTypeFilter] = useState('Tarot');

  const { data: systems = [] } = useQuery<CorrespondenceSystem[]>({
    queryKey: ['correspondence-systems'],
    queryFn: getCorrespondenceSystems,
  });

  // Deck-type filter: only offer types that actually have systems,
  // defaulting to Tarot (or the first available type if no Tarot
  // systems exist).
  const availableTypes = useMemo(() => {
    const types = [...new Set(systems.map(s => s.cartomancy_type || 'Tarot'))];
    types.sort((a, b) => (a === 'Tarot' ? -1 : b === 'Tarot' ? 1 : a.localeCompare(b)));
    return types;
  }, [systems]);
  const activeType = availableTypes.includes(typeFilter)
    ? typeFilter
    : (availableTypes[0] ?? 'Tarot');
  const typedSystems = useMemo(
    () => systems.filter(s => (s.cartomancy_type || 'Tarot') === activeType),
    [systems, activeType],
  );

  const changeType = (t: string) => {
    setTypeFilter(t);
    // Selections belong to the previous type; reset so the first
    // system of the new type auto-selects.
    setSelectedSystemId(null);
    setCompareIds([]);
  };

  // Auto-select first system of the active type (also covers the
  // selected system disappearing when the type changes)
  if (typedSystems.length > 0 &&
      (selectedSystemId === null || !typedSystems.some(s => s.id === selectedSystemId))) {
    setSelectedSystemId(typedSystems[0].id);
  }

  const { data: systemDetail } = useQuery({
    queryKey: ['correspondence-system', selectedSystemId],
    queryFn: () => getCorrespondenceSystem(selectedSystemId!),
    enabled: selectedSystemId !== null && viewMode === 'by-system',
  });

  const { data: compareData = [] } = useQuery<CorrespondenceAssignment[]>({
    queryKey: ['correspondence-compare', compareIds],
    queryFn: () => compareCorrespondenceSystems(compareIds),
    enabled: compareIds.length >= 2 && viewMode === 'compare',
  });

  const toggleCompareId = (id: number) => {
    setCompareIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  // Build table data for by-system view — aggregate multiple values per field
  const bySystemRows = new Map<number, { name: string; fields: Map<string, string[]> }>();
  if (systemDetail?.assignments) {
    for (const a of systemDetail.assignments as CorrespondenceAssignment[]) {
      if (!bySystemRows.has(a.archetype_id)) {
        bySystemRows.set(a.archetype_id, { name: a.archetype_name, fields: new Map() });
      }
      const fieldMap = bySystemRows.get(a.archetype_id)!.fields;
      if (!fieldMap.has(a.field_name)) fieldMap.set(a.field_name, []);
      const values = fieldMap.get(a.field_name)!;
      if (!values.includes(a.field_value)) values.push(a.field_value);
    }
  }

  // The type's archetypes give its suit/rank groups (sections below).
  const { data: typeArchetypes = [] } = useQuery<Archetype[]>({
    queryKey: ['archetypes', activeType],
    queryFn: () => getArchetypes(activeType),
  });

  // Detect group-level patterns, sectioned by this type's own groups
  const patternSections = useMemo<PatternCategorySection[]>(() => {
    if (!systemDetail?.assignments) return [];
    const patterns = detectGroupPatterns(systemDetail.assignments as CorrespondenceAssignment[]);
    return patternsByCategory(patterns, getBulkGroups(activeType, typeArchetypes));
  }, [systemDetail, activeType, typeArchetypes]);

  const filteredArchetypeIds = [...bySystemRows.keys()].filter(id => {
    if (!filterText) return true;
    return bySystemRows.get(id)!.name.toLowerCase().includes(filterText.toLowerCase());
  });

  // Only show columns that have at least one value in this system — empty
  // fields clutter the view for systems that don't use them.
  const visibleFields = CORRESPONDENCE_FIELDS.filter(f => {
    for (const row of bySystemRows.values()) {
      const vals = row.fields.get(f);
      if (vals && vals.length > 0) return true;
    }
    return false;
  });

  // Build compare table data — grouped by archetype, then by system, aggregating multiple values per field
  const compareRows = new Map<string, Map<string, Map<string, string[]>>>();
  const compareSystemNames = new Map<number, string>();
  for (const a of compareData) {
    if (!compareRows.has(a.archetype_name)) {
      compareRows.set(a.archetype_name, new Map());
    }
    const systemName = (a as CorrespondenceAssignment & { system_name?: string }).system_name || String(a.system_id);
    compareSystemNames.set(a.system_id, systemName);
    const sysMap = compareRows.get(a.archetype_name)!;
    if (!sysMap.has(systemName)) {
      sysMap.set(systemName, new Map());
    }
    const fieldMap = sysMap.get(systemName)!;
    if (!fieldMap.has(a.field_name)) fieldMap.set(a.field_name, []);
    const values = fieldMap.get(a.field_name)!;
    if (!values.includes(a.field_value)) values.push(a.field_value);
  }

  const compareSystemList = [...compareSystemNames.entries()].sort((a, b) => a[1].localeCompare(b[1]));

  return (
    <div className="reference-section">
      <div className="corr-viewer__header">
        <h2 className="reference-section__title">Correspondences</h2>
        {availableTypes.length > 1 && (
          <select
            className="corr-viewer__type-select"
            value={activeType}
            onChange={e => changeType(e.target.value)}
            title="Deck type"
          >
            {availableTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        )}
        {onEditCorrespondences && (
          <button
            className="corr-viewer__edit-btn"
            onClick={() => onEditCorrespondences('correspondences')}
          >
            Edit Correspondences
          </button>
        )}
      </div>

      {/* View mode tabs */}
      <div className="corr-viewer__mode-tabs">
        <button
          className={`corr-viewer__mode-tab ${viewMode === 'by-system' ? 'corr-viewer__mode-tab--active' : ''}`}
          onClick={() => setViewMode('by-system')}
        >
          By System
        </button>
        <button
          className={`corr-viewer__mode-tab ${viewMode === 'compare' ? 'corr-viewer__mode-tab--active' : ''}`}
          onClick={() => setViewMode('compare')}
        >
          Compare Systems
        </button>
      </div>

      {/* By System view */}
      {viewMode === 'by-system' && (
        <div className="reference-section__card">
          <div className="corr-viewer__controls">
            <select
              value={selectedSystemId ?? ''}
              onChange={e => setSelectedSystemId(Number(e.target.value))}
              className="corr-viewer__system-select"
            >
              {typedSystems.map(sys => (
                <option key={sys.id} value={sys.id}>{sys.name}</option>
              ))}
            </select>
            <input
              type="text"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              placeholder="Filter cards..."
              className="corr-viewer__filter"
            />
          </div>

          {/* Group-level patterns summary */}
          {patternSections.length > 0 && (
            <div className="corr-viewer__group-summary">
              <h4 className="corr-viewer__group-title">Group Patterns</h4>
              {patternSections.map(section => (
                <div key={section.category} className="corr-viewer__group-category">
                  <div className="corr-viewer__group-category-heading">{section.category}</div>
                  {section.groups.map(({ groupLabel, patterns }) => (
                    <div key={groupLabel} className="corr-viewer__group-row">
                      <span className="corr-viewer__group-field">{displayGroupLabel(groupLabel, systemDetail?.naming_style)}</span>
                      <div className="corr-viewer__group-values">
                        {patterns.map(p => (
                          <span key={p.fieldLabel} className="corr-viewer__group-tag">
                            <span className="corr-viewer__group-name">{p.fieldLabel}</span>
                            <span className="corr-viewer__group-eq">=</span>
                            <span className="corr-viewer__group-val">{p.value}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          <div className="corr-viewer__table-wrap">
            <table className="corr-viewer__table">
              <thead>
                <tr>
                  <th className="corr-viewer__th--card">Card</th>
                  {visibleFields.map(f => (
                    <th key={f}>{CORRESPONDENCE_FIELD_LABELS[f]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredArchetypeIds.map(archId => {
                  const row = bySystemRows.get(archId)!;
                  return (
                    <tr key={archId}>
                      <td className="corr-viewer__td--card">{displayArchetypeName(row.name, systemDetail?.naming_style)}</td>
                      {visibleFields.map(f => (
                        <td key={f} className="corr-viewer__td--value">
                          {(row.fields.get(f) || []).join(', ')}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {filteredArchetypeIds.length === 0 && (
            <p className="reference-section__hint" style={{ textAlign: 'center', padding: 20 }}>
              {filterText ? 'No cards match your filter.' : 'No assignments in this system.'}
            </p>
          )}
        </div>
      )}

      {/* Compare view */}
      {viewMode === 'compare' && (
        <div className="reference-section__card">
          <p className="reference-section__hint">Select two or more systems to compare.</p>
          <div className="corr-viewer__compare-select">
            {typedSystems.map(sys => (
              <label key={sys.id} className="corr-viewer__compare-check">
                <input
                  type="checkbox"
                  checked={compareIds.includes(sys.id)}
                  onChange={() => toggleCompareId(sys.id)}
                />
                <span>{sys.name}</span>
              </label>
            ))}
          </div>

          {compareIds.length >= 2 && compareRows.size > 0 && (
            <div className="corr-viewer__table-wrap">
              <table className="corr-viewer__table">
                <thead>
                  <tr>
                    <th className="corr-viewer__th--card">Card</th>
                    <th>Field</th>
                    {compareSystemList.map(([id, name]) => (
                      <th key={id}>{name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...compareRows.entries()].map(([archName, systemMap]) => {
                    // Find fields that differ across systems
                    const allFields = new Set<string>();
                    for (const fields of systemMap.values()) {
                      for (const f of fields.keys()) allFields.add(f);
                    }

                    return [...allFields].map((fieldName, fi) => (
                      <tr key={`${archName}-${fieldName}`}>
                        {fi === 0 ? (
                          <td className="corr-viewer__td--card" rowSpan={allFields.size}>
                            {archName}
                          </td>
                        ) : null}
                        <td className="corr-viewer__td--field">
                          {CORRESPONDENCE_FIELD_LABELS[fieldName] || fieldName}
                        </td>
                        {compareSystemList.map(([, sysName]) => {
                          const vals = systemMap.get(sysName)?.get(fieldName) || [];
                          const val = vals.join(', ');
                          return <td key={sysName} className="corr-viewer__td--value">{val}</td>;
                        })}
                      </tr>
                    ));
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
