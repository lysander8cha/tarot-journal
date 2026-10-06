import type { Profile } from '../../types';

interface QuerentPickerProps {
  value: number[];
  onChange: (ids: number[]) => void;
  profiles: Profile[];
}

/** An ordered list of querents: one dropdown per person, "+ Add", ×.
 *  A 0 id is a row the user added but hasn't chosen yet. */
export default function QuerentPicker({ value, onChange, profiles }: QuerentPickerProps) {
  return (
    <div className="entry-editor__querents-list">
      {value.map((qId, idx) => (
        <div key={idx} className="entry-editor__querent-row">
          <select
            value={qId || ''}
            onChange={(e) => {
              const newId = e.target.value ? Number(e.target.value) : 0;
              onChange(value.map((id, i) => (i === idx ? newId : id)));
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
            onClick={() => onChange(value.filter((_, i) => i !== idx))}
            title="Remove querent"
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className="entry-editor__add-querent-btn"
        onClick={() => onChange([...value, 0])}
      >
        + Add Querent
      </button>
    </div>
  );
}
