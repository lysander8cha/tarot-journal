import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import Modal, { ModalCancelButton } from '../common/Modal';
import './AnkiExportModal.css';

interface FieldOption {
  key: string;
  label: string;
  always?: boolean;
  populated?: boolean;
}

interface AnkiExportModalProps {
  deckId: number;
  deckName: string;
  onClose: () => void;
}

function FieldRow({
  field,
  checked,
  onToggle,
  dragging,
  dragOver,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  field: FieldOption;
  checked: boolean;
  onToggle: () => void;
  dragging: boolean;
  dragOver: boolean;
  onDragStart: () => void;
  onDragOver: () => void;
  onDrop: () => void;
  onDragEnd: () => void;
}) {
  const cls = [
    'anki-export__field-row',
    dragging ? 'anki-export__field-row--dragging' : '',
    dragOver ? 'anki-export__field-row--drag-over' : '',
  ].filter(Boolean).join(' ');

  return (
    <div
      className={cls}
      draggable
      onDragStart={onDragStart}
      onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; onDragOver(); }}
      onDrop={e => { e.preventDefault(); onDrop(); }}
      onDragEnd={onDragEnd}
    >
      <span className="anki-export__drag-handle" aria-hidden="true">
        ⠿
      </span>
      <label className="anki-export__field-label">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          disabled={field.always}
        />
        <span>{field.label}</span>
        {field.populated && <span className="anki-export__badge">has data</span>}
        {field.always && <span className="anki-export__badge anki-export__badge--required">required</span>}
      </label>
    </div>
  );
}

export default function AnkiExportModal({ deckId, deckName, onClose }: AnkiExportModalProps) {
  const [orderedFields, setOrderedFields] = useState<FieldOption[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const { data: availableFields = [], isLoading } = useQuery<FieldOption[]>({
    queryKey: ['anki-fields', deckId],
    queryFn: async () => {
      const res = await api.get(`/api/decks/${deckId}/anki-fields`);
      return res.data;
    },
  });

  // Initialize field order and selection when data loads
  useEffect(() => {
    if (availableFields.length > 0 && orderedFields.length === 0) {
      setOrderedFields(availableFields);
      // Select always-required fields plus any populated ones
      const initial = new Set<string>();
      for (const f of availableFields) {
        if (f.always || f.populated) {
          initial.add(f.key);
        }
      }
      setSelectedKeys(initial);
    }
  }, [availableFields, orderedFields.length]);

  const [draggedKey, setDraggedKey] = useState<string | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  const endDrag = () => { setDraggedKey(null); setDragOverKey(null); };

  // Move the dragged field into the drop target's slot.
  const handleDrop = (targetKey: string) => {
    if (draggedKey != null && draggedKey !== targetKey) {
      setOrderedFields(prev => {
        const from = prev.findIndex(f => f.key === draggedKey);
        const to = prev.findIndex(f => f.key === targetKey);
        if (from < 0 || to < 0) return prev;
        const next = [...prev];
        next.splice(to, 0, ...next.splice(from, 1));
        return next;
      });
    }
    endDrag();
  };

  const toggleField = (key: string) => {
    setSelectedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleExport = async () => {
    const fields = orderedFields
      .filter(f => selectedKeys.has(f.key))
      .map(f => f.key);

    if (fields.length === 0) {
      setError('Select at least one field.');
      return;
    }

    setExporting(true);
    setError('');
    try {
      const res = await api.post(
        `/api/decks/${deckId}/anki-export`,
        { fields },
        { responseType: 'blob' },
      );
      // Trigger download
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      const safeName = deckName.replace(/[^a-zA-Z0-9 _-]/g, '').trim();
      a.download = `${safeName}_anki.zip`;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch {
      setError('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const selectedCount = orderedFields.filter(f => selectedKeys.has(f.key)).length;

  return (
    <Modal open={true} onClose={onClose} isDirty={false}>
      <div className="anki-export">
        <h2 className="anki-export__title">Export for Anki</h2>
        <p className="anki-export__hint">
          Select and reorder fields for the Anki export. Drag to reorder — column
          order in the export matches this order. The exported zip contains a
          tab-separated text file and card images.
        </p>

        {error && (
          <div className="anki-export__error">{error}</div>
        )}

        {isLoading ? (
          <div className="anki-export__loading">Loading fields...</div>
        ) : (
          <>
            <div className="anki-export__field-list">
              {orderedFields.map(field => (
                <FieldRow
                  key={field.key}
                  field={field}
                  checked={selectedKeys.has(field.key)}
                  onToggle={() => toggleField(field.key)}
                  dragging={draggedKey === field.key}
                  dragOver={dragOverKey === field.key && draggedKey !== field.key}
                  onDragStart={() => setDraggedKey(field.key)}
                  onDragOver={() => { if (dragOverKey !== field.key) setDragOverKey(field.key); }}
                  onDrop={() => handleDrop(field.key)}
                  onDragEnd={endDrag}
                />
              ))}
            </div>

            <div className="anki-export__footer">
              <span className="anki-export__count">
                {selectedCount} field{selectedCount !== 1 ? 's' : ''} selected
              </span>
              <div className="anki-export__actions">
                <ModalCancelButton>Cancel</ModalCancelButton>
                <button
                  className="anki-export__export-btn"
                  onClick={handleExport}
                  disabled={exporting || selectedCount === 0}
                >
                  {exporting ? 'Exporting...' : 'Export'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
