import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { addFollowUpNote, updateFollowUpNote, deleteFollowUpNote } from '../../api/entries';
import RichTextEditor from '../common/RichTextEditor';
import RichTextViewer from '../common/RichTextViewer';
import type { FollowUpNote } from '../../types';
import './FollowUpNotes.css';

interface FollowUpNotesProps {
  entryId: number;
  notes: FollowUpNote[];
}

export default function FollowUpNotes({ entryId, notes }: FollowUpNotesProps) {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editorContent, setEditorContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleAdd = () => {
    setEditorContent('');
    setEditingNoteId(null);
    setShowAdd(true);
  };

  const handleEdit = (note: FollowUpNote) => {
    setEditorContent(note.content);
    setEditingNoteId(note.id);
    setShowAdd(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      if (editingNoteId) {
        await updateFollowUpNote(editingNoteId, editorContent);
      } else {
        await addFollowUpNote(entryId, editorContent);
      }
      queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
      setShowAdd(false);
      setEditingNoteId(null);
      setEditorContent('');
    } catch (err) {
      console.error('Failed to save note:', err);
      setError('Failed to save note. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noteId: number) => {
    if (!window.confirm('Delete this follow-up note?')) return;
    setError('');
    try {
      await deleteFollowUpNote(noteId);
      queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
    } catch (err) {
      console.error('Failed to delete note:', err);
      setError('Failed to delete note. Please try again.');
    }
  };

  const handleCancel = () => {
    setShowAdd(false);
    setEditingNoteId(null);
    setEditorContent('');
  };

  return (
    <div className="follow-up-notes">
      <div className="follow-up-notes__header">
        <h3 className="follow-up-notes__title">Follow-up Notes</h3>
        {!showAdd && (
          <button className="follow-up-notes__add-btn" onClick={handleAdd}>
            + Add Note
          </button>
        )}
      </div>

      {error && <div className="follow-up-notes__error">{error}</div>}

      {showAdd && (
        <div className="follow-up-notes__editor">
          <RichTextEditor
            content={editorContent}
            onChange={setEditorContent}
            placeholder="Write a follow-up note..."
            minHeight={80}
          />
          <div className="follow-up-notes__editor-actions">
            <button onClick={handleCancel}>Cancel</button>
            <button className="primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : editingNoteId ? 'Update' : 'Add'}
            </button>
          </div>
        </div>
      )}

      {notes.length === 0 && !showAdd && (
        <div className="follow-up-notes__empty">No follow-up notes yet.</div>
      )}

      {notes.map((note) => (
        <div key={note.id} className="follow-up-notes__note">
          <div className="follow-up-notes__note-header">
            <span className="follow-up-notes__note-date">
              {new Date(note.created_at).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </span>
            <div className="follow-up-notes__note-actions">
              <button
                className="follow-up-notes__action-btn"
                onClick={() => handleEdit(note)}
                title="Edit"
              >
                &#9998;
              </button>
              <button
                className="follow-up-notes__action-btn follow-up-notes__action-btn--danger"
                onClick={() => handleDelete(note.id)}
                title="Delete"
              >
                &times;
              </button>
            </div>
          </div>
          <RichTextViewer content={note.content} />
        </div>
      ))}
    </div>
  );
}
