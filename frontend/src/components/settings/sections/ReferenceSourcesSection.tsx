/**
 * Settings → Reference Sources.
 *
 * This page owns the lifecycle of reference sources:
 *  - create / rename / delete sources
 *  - pick which cartomancy types each source covers
 *  - manage the per-type field set on each source (e.g. "Upright
 *    Meaning" + "Reversed" for Tarot, "Meaning" for Lenormand)
 *
 * Per-card / per-archetype CONTENT lives in the Archetype Notes
 * section — pick an archetype there, fill in the editors for each
 * (source, field) pair this source defines for that type.
 *
 * Layout: each source is a collapsible row. Expanding reveals the
 * full metadata + field-manager UI inline.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getReferenceSources,
  createReferenceSource,
  updateReferenceSource,
  deleteReferenceSource,
  getReferenceSourceDependencies,
  getSourceFields,
  createSourceField,
  updateSourceField,
  deleteSourceField,
  reorderSourceFields,
} from '../../../api/referenceSources';
import { useToast } from '../../../context/ToastContext';
import ScribeModal from '../../scribe/ScribeModal';
import { getCartomancyTypes } from '../../../api/decks';
import { orderTypeNames } from '../../../utils/typeOrder';
import type { CartomancyType, ReferenceSource, SourceField } from '../../../types';
import '../SettingsTab.css';
import './ReferenceSourcesSection.css';
import { confirmDialog } from '../../common/ConfirmDialog';
import Modal, { ModalCancelButton } from '../../common/Modal';


export default function ReferenceSourcesSection() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const { data: sources = [] } = useQuery<ReferenceSource[]>({
    queryKey: ['reference-sources'],
    queryFn: () => getReferenceSources(),
  });
  // Every deck type — built-in or user-created — can take sources.
  const { data: allTypes = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const supportedTypes = useMemo(
    () => orderTypeNames(allTypes.map(t => t.name)),
    [allTypes],
  );
  // Any cache touching source-shaped data needs to refetch when the
  // source list / metadata changes. The Archetype Notes page reads
  // from these same caches.
  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['reference-sources'] });
    queryClient.invalidateQueries({ queryKey: ['source-fields'] });
    queryClient.invalidateQueries({ queryKey: ['archetype-source-entries'] });
  }, [queryClient]);

  // === Add Source flow ====================================================
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [newAuthors, setNewAuthors] = useState('');
  const [newTypes, setNewTypes] = useState<string[]>(['Tarot']);

  const handleAdd = async () => {
    const name = newName.trim();
    if (!name) return;
    if (newTypes.length === 0) {
      showToast('Pick at least one cartomancy type.');
      return;
    }
    const authors = newAuthors.split(/[,;\n]/).map(s => s.trim()).filter(Boolean);
    try {
      const { id } = await createReferenceSource({ name, cartomancy_types: newTypes, authors });
      setNewName('');
      setNewAuthors('');
      setNewTypes(['Tarot']);
      setAdding(false);
      invalidateAll();
      // The list is alphabetical, so the new row usually lands far
      // from the add form at the bottom — scroll to it and flash it,
      // expanded and ready for field setup, so it's unmissable.
      setExpandedId(id);
      setJustAddedId(id);
      window.setTimeout(() => setJustAddedId(null), 2500);
    } catch {
      showToast('Could not add source (name may already exist).');
    }
  };

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ReferenceSource | null>(null);
  const [scribeTarget, setScribeTarget] = useState<ReferenceSource | null>(null);

  return (
    <div className="settings-tab__scroll reference-sources">
      <h2 className="settings-tab__title">Reference Sources</h2>
      <p className="settings-tab__hint">
        A reference source is anything you cite when authoring per-card content
        — a book, website, blog post, your own teacher's notes. Configure the
        source here: which cartomancy types it covers, and what fields it
        defines for each type (e.g. "Upright Meaning" + "Reversed" for Tarot).
        Fill in the per-card content over in <strong>Archetype Notes</strong>.
      </p>

      <section className="settings-tab__section">
        {sources.length === 0 && !adding && (
          <p className="reference-sources__empty">No sources yet.</p>
        )}

        <ul className="reference-sources__list">
          {sources.map(s => (
            <SourceRow
              key={s.id}
              source={s}
              highlight={justAddedId === s.id}
              expanded={expandedId === s.id}
              onToggle={() =>
                setExpandedId(prev => (prev === s.id ? null : s.id))
              }
              onDeleteRequest={() => setDeleteTarget(s)}
              onScribeRequest={() => setScribeTarget(s)}
              onChanged={invalidateAll}
            />
          ))}
        </ul>

        {adding ? (
          <div className="reference-sources__add-card">
            <label className="settings-tab__label">Name</label>
            <input
              autoFocus
              placeholder="e.g. Pollack, 78 Degrees of Wisdom"
              value={newName}
              onChange={e => setNewName(e.target.value)}
            />
            <label className="settings-tab__label">Authors</label>
            <input
              placeholder="Optional — comma- or semicolon-separated"
              value={newAuthors}
              onChange={e => setNewAuthors(e.target.value)}
            />
            <label className="settings-tab__label">Cartomancy Types</label>
            <div className="reference-sources__type-grid">
              {supportedTypes.map(t => (
                <label key={t} className="reference-sources__type-toggle">
                  <input
                    type="checkbox"
                    checked={newTypes.includes(t)}
                    onChange={() =>
                      setNewTypes(prev =>
                        prev.includes(t)
                          ? prev.filter(x => x !== t)
                          : [...prev, t],
                      )
                    }
                  />
                  <span>{t}</span>
                </label>
              ))}
            </div>
            <p className="settings-tab__hint">
              A source can cover more than one type. Each type gets its own
              field set you'll configure after creating it.
            </p>
            <div className="reference-sources__add-actions">
              <button onClick={handleAdd} disabled={!newName.trim() || newTypes.length === 0}>
                Add
              </button>
              <button
                onClick={() => {
                  setAdding(false);
                  setNewName('');
                  setNewAuthors('');
                  setNewTypes(['Tarot']);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="reference-sources__add-btn"
          >
            + Add Source
          </button>
        )}
      </section>

      {scribeTarget && (
        <ScribeModal
          source={scribeTarget}
          open
          onClose={() => setScribeTarget(null)}
        />
      )}

      {deleteTarget && (
        <DeleteDialog
          source={deleteTarget}
          otherSources={sources.filter(s => s.id !== deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => {
            setDeleteTarget(null);
            invalidateAll();
            if (expandedId === deleteTarget.id) setExpandedId(null);
          }}
          showToast={showToast}
        />
      )}
    </div>
  );
}

// =================================================================
// One source row — header bar that expands to show metadata + fields
// =================================================================

function SourceRow({
  source,
  expanded,
  highlight = false,
  onToggle,
  onDeleteRequest,
  onScribeRequest,
  onChanged,
}: {
  source: ReferenceSource;
  expanded: boolean;
  /** Freshly added: scroll into view and flash, so the alphabetical
   *  landing spot (often far from the add form) is unmissable. */
  highlight?: boolean;
  onToggle: () => void;
  onDeleteRequest: () => void;
  onScribeRequest: () => void;
  onChanged: () => void;
}) {
  const rowRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (highlight) rowRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [highlight]);
  return (
    <li
      ref={rowRef}
      className={`reference-sources__row ${highlight ? 'reference-sources__row--flash' : ''}`}
    >
      <div className="reference-sources__row-head">
        <button
          type="button"
          className="reference-sources__row-toggle"
          onClick={onToggle}
          aria-expanded={expanded}
        >
          <span
            className={`reference-sources__chevron ${expanded ? 'reference-sources__chevron--open' : ''}`}
            aria-hidden="true"
          >
            ▸
          </span>
          <span className="reference-sources__name">{source.name}</span>
          {source.authors.length > 0 && (
            <span className="reference-sources__authors">
              {source.authors.join('; ')}
            </span>
          )}
          <span className="reference-sources__type-badge">
            {source.cartomancy_types.join(', ')}
          </span>
        </button>
        <button
          onClick={onScribeRequest}
          title="Import this book's content with the AI assistant"
        >
          Import with AI…
        </button>
        <button
          className="danger"
          onClick={onDeleteRequest}
          aria-label={`Delete ${source.name}`}
        >
          Delete
        </button>
      </div>
      {expanded && (
        <SourceEditor source={source} onChanged={onChanged} />
      )}
    </li>
  );
}

// =================================================================
// SourceEditor — metadata form + per-type field manager
// (Used inline by SourceRow when it's expanded.)
// =================================================================

function SourceEditor({
  source,
  onChanged,
}: {
  source: ReferenceSource;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { data: allTypes = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });
  const supportedTypes = useMemo(
    () => orderTypeNames(allTypes.map(t => t.name)),
    [allTypes],
  );

  // Hydrate from the source row on mount + on source-id change.
  const [name, setName] = useState(source.name);
  const [authorsText, setAuthorsText] = useState(source.authors.join(', '));
  const [coveredTypes, setCoveredTypes] = useState<string[]>(source.cartomancy_types);
  const firstSaveSkipRef = useRef(true);
  useEffect(() => {
    firstSaveSkipRef.current = true;
    setName(source.name);
    setAuthorsText(source.authors.join(', '));
    setCoveredTypes(source.cartomancy_types);
  }, [source.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced autosave for the metadata form.
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (firstSaveSkipRef.current) {
      firstSaveSkipRef.current = false;
      return;
    }
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      const trimmed = name.trim();
      if (!trimmed) return;
      if (coveredTypes.length === 0) return;
      const authors = authorsText
        .split(/[,;\n]/)
        .map(s => s.trim())
        .filter(Boolean);
      try {
        await updateReferenceSource(source.id, {
          name: trimmed,
          authors,
          cartomancy_types: coveredTypes,
        });
        onChanged();
      } catch (err) {
        console.error('Failed to save source metadata:', err);
        showToast('Failed to save source.');
      }
    }, 500);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [name, authorsText, coveredTypes, source.id, onChanged, showToast]);

  const toggleType = (type: string) => {
    setCoveredTypes(prev => {
      if (prev.includes(type)) {
        if (prev.length === 1) return prev;
        return prev.filter(t => t !== type);
      }
      return [...prev, type];
    });
  };

  return (
    <div className="reference-sources__editor">
      <div className="reference-sources__field">
        <label className="settings-tab__label">Name</label>
        <input value={name} onChange={e => setName(e.target.value)} />
      </div>
      <div className="reference-sources__field">
        <label className="settings-tab__label">Authors</label>
        <input
          value={authorsText}
          placeholder="e.g. Rachel Pollack, Mary K. Greer"
          onChange={e => setAuthorsText(e.target.value)}
        />
        <p className="settings-tab__hint">
          Comma- or semicolon-separated. Order is preserved.
        </p>
      </div>
      <div className="reference-sources__field">
        <label className="settings-tab__label">Cartomancy Types</label>
        <div className="reference-sources__type-grid">
          {supportedTypes.map(t => (
            <label key={t} className="reference-sources__type-toggle">
              <input
                type="checkbox"
                checked={coveredTypes.includes(t)}
                disabled={coveredTypes.length === 1 && coveredTypes.includes(t)}
                onChange={() => toggleType(t)}
              />
              <span>{t}</span>
            </label>
          ))}
        </div>
        <p className="settings-tab__hint">
          Dropping a type also removes the fields and per-card content
          scoped to it.
        </p>
      </div>

      {coveredTypes.map(t => (
        <FieldsManager
          key={t}
          source={source}
          cartomancyType={t}
          invalidateOuter={() => {
            queryClient.invalidateQueries({
              queryKey: ['source-fields', source.id, t],
            });
            onChanged();
          }}
        />
      ))}
    </div>
  );
}

// =================================================================
// FieldsManager — add / rename / delete fields for one (source, type)
// =================================================================

function FieldsManager({
  source,
  cartomancyType,
  invalidateOuter,
}: {
  source: ReferenceSource;
  cartomancyType: string;
  invalidateOuter: () => void;
}) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [newName, setNewName] = useState('');
  const [newCollapsible, setNewCollapsible] = useState(false);

  const { data: fields = [] } = useQuery<SourceField[]>({
    queryKey: ['source-fields', source.id, cartomancyType],
    queryFn: () => getSourceFields(source.id, cartomancyType),
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['source-fields', source.id, cartomancyType] });
    queryClient.invalidateQueries({ queryKey: ['archetype-source-entries'] });
    invalidateOuter();
  }, [queryClient, source.id, cartomancyType, invalidateOuter]);

  // Drag-and-drop reordering (same HTML5 DnD pattern as the
  // Correspondences editor's column headers).
  const [draggedFieldId, setDraggedFieldId] = useState<number | null>(null);
  const [dragOverFieldId, setDragOverFieldId] = useState<number | null>(null);

  const handleFieldDrop = useCallback(async (targetId: number) => {
    const fromId = draggedFieldId;
    setDraggedFieldId(null);
    setDragOverFieldId(null);
    if (fromId === null || fromId === targetId) return;

    const ids = fields.map(f => f.id);
    const fromIdx = ids.indexOf(fromId);
    const toIdx = ids.indexOf(targetId);
    if (fromIdx === -1 || toIdx === -1) return;
    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, fromId);

    // Optimistically show the new order so the row lands where it was
    // dropped instantly; the refetch after saving confirms it.
    const byId = new Map(fields.map(f => [f.id, f]));
    queryClient.setQueryData<SourceField[]>(
      ['source-fields', source.id, cartomancyType],
      ids.map(id => byId.get(id)!),
    );

    try {
      await reorderSourceFields(source.id, cartomancyType, ids);
    } catch (err) {
      console.error('Failed to reorder fields:', err);
      showToast('Failed to reorder fields.');
    } finally {
      invalidate();
    }
  }, [draggedFieldId, fields, source.id, cartomancyType, queryClient, invalidate, showToast]);

  const handleAdd = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      await createSourceField(source.id, {
        name,
        cartomancy_type: cartomancyType,
        collapsible: newCollapsible,
      });
      setNewName('');
      setNewCollapsible(false);
      invalidate();
    } catch (err) {
      console.error('Failed to create field:', err);
      showToast('Could not add field (name may already be used on this type).');
    }
  }, [newName, newCollapsible, source.id, cartomancyType, invalidate, showToast]);

  const handleDelete = useCallback(
    async (field: SourceField) => {
      if (
        !(await confirmDialog(
          `Delete the "${field.name}" field?\n\n` +
            `All content authored under this field across every card will be removed. This cannot be undone.`,
        ))
      ) {
        return;
      }
      try {
        await deleteSourceField(field.id);
        invalidate();
      } catch (err) {
        console.error('Failed to delete field:', err);
        showToast('Failed to delete field.');
      }
    },
    [invalidate, showToast],
  );

  return (
    <div className="reference-sources__fields-manager">
      <h4 className="reference-sources__fields-title">
        Fields for {cartomancyType}
      </h4>
      {fields.length === 0 ? (
        <p className="reference-sources__empty">
          No {cartomancyType} fields yet.
        </p>
      ) : (
        <ul className="reference-sources__fields-list">
          {fields.map(f => (
            <FieldRow
              key={f.id}
              field={f}
              onChanged={invalidate}
              onDelete={handleDelete}
              dragging={draggedFieldId === f.id}
              dragOver={dragOverFieldId === f.id && draggedFieldId !== f.id}
              onDragStart={() => setDraggedFieldId(f.id)}
              onDragOver={() => {
                if (draggedFieldId !== null && draggedFieldId !== f.id) {
                  setDragOverFieldId(f.id);
                }
              }}
              onDrop={() => handleFieldDrop(f.id)}
              onDragEnd={() => {
                setDraggedFieldId(null);
                setDragOverFieldId(null);
              }}
            />
          ))}
        </ul>
      )}

      <div className="reference-sources__new-field">
        <input
          value={newName}
          placeholder={`New ${cartomancyType} field name…`}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd(); }}
        />
        <label
          className="reference-sources__field-collapsible-toggle"
          title="When set, the Archetype Notes editor renders this field as a chevron disclosure (collapsed by default)."
        >
          <input
            type="checkbox"
            checked={newCollapsible}
            onChange={e => setNewCollapsible(e.target.checked)}
          />
          <span>Collapsible</span>
        </label>
        <button onClick={handleAdd} disabled={!newName.trim()}>
          + Add Field
        </button>
      </div>
    </div>
  );
}

function FieldRow({
  field,
  onChanged,
  onDelete,
  dragging,
  dragOver,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  field: SourceField;
  onChanged: () => void;
  onDelete: (f: SourceField) => void;
  dragging: boolean;
  dragOver: boolean;
  onDragStart: () => void;
  onDragOver: () => void;
  onDrop: () => void;
  onDragEnd: () => void;
}) {
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(field.name);
  useEffect(() => { setDraft(field.name); }, [field.name]);

  const save = useCallback(async () => {
    const name = draft.trim();
    if (!name || name === field.name) {
      setEditing(false);
      setDraft(field.name);
      return;
    }
    try {
      await updateSourceField(field.id, { name });
      setEditing(false);
      onChanged();
    } catch (err) {
      console.error('Failed to rename field:', err);
      showToast('Could not rename field.');
    }
  }, [draft, field.id, field.name, onChanged, showToast]);

  // Inline-autosave on the collapsible flag — toggling shouldn't
  // need an explicit "save" step. Optimistic flip is fine because
  // backend can't reject the bool (no validation).
  const handleToggleCollapsible = useCallback(async () => {
    const next = !field.collapsible;
    try {
      await updateSourceField(field.id, { collapsible: !!next });
      onChanged();
    } catch (err) {
      console.error('Failed to toggle collapsible:', err);
      showToast('Could not update field.');
    }
  }, [field.id, field.collapsible, onChanged, showToast]);

  return (
    <li
      className={`reference-sources__field-row${dragging ? ' reference-sources__field-row--dragging' : ''}${dragOver ? ' reference-sources__field-row--drag-over' : ''}`}
      // Not draggable while renaming, so drag doesn't fight with text
      // selection in the input.
      draggable={!editing}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = 'move';
        onDragStart();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        onDragOver();
      }}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
      onDragEnd={onDragEnd}
    >
      {!editing && (
        <span className="reference-sources__field-drag-handle" aria-hidden="true" title="Drag to reorder">
          ⋮⋮
        </span>
      )}
      {editing ? (
        <>
          <input
            autoFocus
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') save();
              if (e.key === 'Escape') { setDraft(field.name); setEditing(false); }
            }}
          />
          <button onClick={save}>Save</button>
          <button onClick={() => { setDraft(field.name); setEditing(false); }}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <span className="reference-sources__field-row-name">{field.name}</span>
          <label
            className="reference-sources__field-collapsible-toggle"
            title="When set, the Archetype Notes editor renders this field as a chevron disclosure (collapsed by default)."
          >
            <input
              type="checkbox"
              checked={!!field.collapsible}
              onChange={handleToggleCollapsible}
            />
            <span>Collapsible</span>
          </label>
          <button onClick={() => setEditing(true)}>Rename</button>
          <button className="danger" onClick={() => onDelete(field)}>
            Delete
          </button>
        </>
      )}
    </li>
  );
}

// =================================================================
// DeleteDialog — keeps the reassign-or-unsource behaviour from before
// =================================================================

function DeleteDialog({
  source,
  otherSources,
  onClose,
  onDeleted,
  showToast,
}: {
  source: ReferenceSource;
  otherSources: ReferenceSource[];
  onClose: () => void;
  onDeleted: () => void;
  showToast: (msg: string) => void;
}) {
  const { data: deps = { combination_meanings: 0, archetype_source_entries: 0 } } =
    useQuery({
      queryKey: ['reference-source-deps', source.id],
      queryFn: () => getReferenceSourceDependencies(source.id),
    });
  const total = deps.combination_meanings + deps.archetype_source_entries;
  const [reassignTo, setReassignTo] = useState<'unsource' | number>('unsource');

  const handleDelete = async () => {
    try {
      await deleteReferenceSource(
        source.id,
        reassignTo === 'unsource' ? undefined : reassignTo,
      );
      onDeleted();
    } catch {
      showToast('Could not delete source.');
    }
  };

  return (
    <Modal open onClose={onClose} title={`Delete source "${source.name}"?`} width={480}>
      <div className="reference-sources__dialog">
        {total === 0 ? (
          <p>No entries reference this source. Deletion is safe.</p>
        ) : (
          <>
            <p>
              {total} entr{total === 1 ? 'y references' : 'ies reference'} this source
              {deps.combination_meanings > 0 && (
                <> ({deps.combination_meanings} combination meaning{deps.combination_meanings === 1 ? '' : 's'}</>
              )}
              {deps.combination_meanings > 0 && deps.archetype_source_entries > 0 && ', '}
              {deps.archetype_source_entries > 0 && (
                <>{deps.archetype_source_entries} per-card entr{deps.archetype_source_entries === 1 ? 'y' : 'ies'}</>
              )}
              {(deps.combination_meanings > 0 || deps.archetype_source_entries > 0) && ')'}.
              The entries themselves will not be deleted — pick what should
              happen to their source label:
            </p>
            <label className="reference-sources__dialog-option">
              <input
                type="radio"
                name="reassign"
                checked={reassignTo === 'unsource'}
                onChange={() => setReassignTo('unsource')}
              />
              Make those entries unsourced
            </label>
            {otherSources.map(s => (
              <label key={s.id} className="reference-sources__dialog-option">
                <input
                  type="radio"
                  name="reassign"
                  checked={reassignTo === s.id}
                  onChange={() => setReassignTo(s.id)}
                />
                Reassign to "{s.name}"
              </label>
            ))}
          </>
        )}
        <div className="reference-sources__dialog-actions">
          <ModalCancelButton>Cancel</ModalCancelButton>
          <button onClick={handleDelete} className="danger">Delete</button>
        </div>
      </div>
    </Modal>
  );
}

