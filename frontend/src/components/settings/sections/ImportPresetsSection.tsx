import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getImportPresetsDetails,
  saveImportPreset,
  deleteImportPreset,
  resetImportPreset,
  type ImportPresetDetail,
} from '../../../api/importExport';
import { getCartomancyTypes } from '../../../api/decks';
import type { CartomancyType } from '../../../types';
import MappingsEditor from '../MappingsEditor';
import '../SettingsTab.css';
import { confirmDialog } from '../../common/ConfirmDialog';

const SUIT_KEYS_BY_TYPE: Record<string, string[]> = {
  Tarot: ['wands', 'cups', 'swords', 'pentacles'],
  'Playing Cards': ['hearts', 'diamonds', 'clubs', 'spades'],
  'Petit Lenormand': ['hearts', 'diamonds', 'clubs', 'spades'],
  'Playing Cards (Latin-suited)': ['coins', 'cups', 'swords', 'batons'],
  'Playing Cards (German-suited)': ['hearts', 'bells', 'leaves', 'acorns'],
};

export default function ImportPresetsSection() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const { data: importPresets = [] } = useQuery<ImportPresetDetail[]>({
    queryKey: ['import-presets-details'],
    queryFn: getImportPresetsDetails,
  });

  const { data: cartomancyTypes = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });

  const [editingPreset, setEditingPreset] = useState<ImportPresetDetail | null>(null);
  const [presetForm, setPresetForm] = useState({
    name: '',
    type: 'Tarot',
    description: '',
    suit_names: {} as Record<string, string>,
    mappings_grouped: {} as Record<string, string[]>,
  });
  const [showMappings, setShowMappings] = useState(false);
  const [presetSaving, setPresetSaving] = useState(false);

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const startEditPreset = (preset: ImportPresetDetail) => {
    setEditingPreset(preset);
    setPresetForm({
      name: preset.name.replace('Custom: ', ''),
      type: preset.type,
      description: preset.description,
      suit_names: { ...preset.suit_names },
      mappings_grouped: { ...preset.mappings_grouped },
    });
    setShowMappings(false);
  };

  const startNewPreset = () => {
    setEditingPreset({ name: '', type: 'Tarot', description: '', suit_names: {}, card_count: 0, is_builtin: false, is_customized: false, mappings_grouped: {} });
    setPresetForm({
      name: '',
      type: 'Tarot',
      description: '',
      suit_names: {},
      mappings_grouped: {},
    });
    setShowMappings(false);
  };

  const cancelEditPreset = () => {
    setEditingPreset(null);
    setShowMappings(false);
  };

  const handleSavePreset = async () => {
    if (!presetForm.name.trim()) {
      showMsg('Preset name is required', 'error');
      return;
    }
    setPresetSaving(true);
    try {
      const flatMappings: Record<string, string> = {};
      for (const [cardName, patterns] of Object.entries(presetForm.mappings_grouped)) {
        for (const pattern of patterns) {
          flatMappings[pattern] = cardName;
        }
      }

      await saveImportPreset({
        name: presetForm.name.trim(),
        type: presetForm.type,
        description: presetForm.description,
        suit_names: presetForm.suit_names,
        mappings: flatMappings,
      });
      queryClient.invalidateQueries({ queryKey: ['import-presets-details'] });
      queryClient.invalidateQueries({ queryKey: ['import-presets'] });
      setEditingPreset(null);
      showMsg('Import preset saved', 'success');
    } catch {
      showMsg('Failed to save import preset', 'error');
    } finally {
      setPresetSaving(false);
    }
  };

  const handleDeletePreset = async (preset: ImportPresetDetail) => {
    const action = preset.is_customized ? 'reset to default' : 'delete';
    if (!(await confirmDialog(`Are you sure you want to ${action} "${preset.name}"?`))) return;
    try {
      if (preset.is_customized) {
        await resetImportPreset(preset.name);
      } else {
        await deleteImportPreset(preset.name);
      }
      queryClient.invalidateQueries({ queryKey: ['import-presets-details'] });
      queryClient.invalidateQueries({ queryKey: ['import-presets'] });
      showMsg(`Import preset ${action === 'delete' ? 'deleted' : 'reset'}`, 'success');
    } catch {
      showMsg(`Failed to ${action} preset`, 'error');
    }
  };

  return (
    <div className="settings-tab__scroll">
      <h2 className="settings-tab__title">Import Presets</h2>

      {message && (
        <div className={`settings-tab__message settings-tab__message--${message.type}`}>
          {message.text}
        </div>
      )}

      <section className="settings-tab__section">
        <p className="settings-tab__hint">
          These presets control how card images are named and organized when importing a deck from a folder.
        </p>

        <div className="settings-tab__preset-list">
          {importPresets.map((preset) => (
            <div key={preset.name} className="settings-tab__import-preset-row">
              <div className="settings-tab__import-preset-info">
                <span className="settings-tab__import-preset-name">
                  {preset.name}
                  {preset.is_customized && (
                    <span className="settings-tab__import-preset-badge">modified</span>
                  )}
                  {!preset.is_builtin && (
                    <span className="settings-tab__import-preset-badge settings-tab__import-preset-badge--custom">custom</span>
                  )}
                </span>
                <span className="settings-tab__import-preset-desc">
                  {preset.description || `${preset.type} · ${preset.card_count} cards`}
                </span>
              </div>
              <div className="settings-tab__import-preset-actions">
                <button
                  className="settings-tab__import-preset-btn"
                  onClick={() => startEditPreset(preset)}
                  title="Edit"
                >
                  Edit
                </button>
                {(preset.is_customized || !preset.is_builtin) && (
                  <button
                    className="settings-tab__import-preset-btn settings-tab__import-preset-btn--danger"
                    onClick={() => handleDeletePreset(preset)}
                    title={preset.is_customized ? 'Reset to default' : 'Delete'}
                  >
                    {preset.is_customized ? 'Reset' : 'Delete'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <button className="settings-tab__add-preset-btn" onClick={startNewPreset}>
          + Add New Preset
        </button>

        {editingPreset && (
          <div className="settings-tab__preset-editor">
            <h4 className="settings-tab__subsection-title">
              {editingPreset.name ? `Edit: ${editingPreset.name}` : 'New Preset'}
            </h4>

            <div className="settings-tab__preset-form">
              <div className="settings-tab__field">
                <label className="settings-tab__label">Name</label>
                <input
                  type="text"
                  value={presetForm.name}
                  onChange={(e) => setPresetForm({ ...presetForm, name: e.target.value })}
                  placeholder="My Custom Preset"
                  disabled={editingPreset.is_builtin}
                />
              </div>

              <div className="settings-tab__field">
                <label className="settings-tab__label">Deck Type</label>
                <select
                  value={presetForm.type}
                  onChange={(e) => {
                    const newType = e.target.value;
                    const defaultSuits = SUIT_KEYS_BY_TYPE[newType];
                    setPresetForm({
                      ...presetForm,
                      type: newType,
                      suit_names: defaultSuits
                        ? Object.fromEntries(defaultSuits.map((k) => [k, k.charAt(0).toUpperCase() + k.slice(1)]))
                        : {},
                    });
                  }}
                  disabled={editingPreset.is_builtin}
                >
                  {cartomancyTypes.map((t) => (
                    <option key={t.id} value={t.name}>{t.name}</option>
                  ))}
                </select>
              </div>

              <div className="settings-tab__field">
                <label className="settings-tab__label">Description</label>
                <input
                  type="text"
                  value={presetForm.description}
                  onChange={(e) => setPresetForm({ ...presetForm, description: e.target.value })}
                  placeholder="Brief description of this preset"
                />
              </div>

              {SUIT_KEYS_BY_TYPE[presetForm.type] && (
                <>
                  <label className="settings-tab__label">Suit Names</label>
                  <div className="settings-tab__suit-grid">
                    {SUIT_KEYS_BY_TYPE[presetForm.type].map((key) => (
                      <div key={key} className="settings-tab__field">
                        <label className="settings-tab__label settings-tab__label--small">
                          {key.charAt(0).toUpperCase() + key.slice(1)}
                        </label>
                        <input
                          type="text"
                          value={presetForm.suit_names[key] || ''}
                          onChange={(e) =>
                            setPresetForm({
                              ...presetForm,
                              suit_names: { ...presetForm.suit_names, [key]: e.target.value },
                            })
                          }
                        />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="settings-tab__mappings-toggle">
              <button
                className="settings-tab__customize-btn"
                onClick={() => setShowMappings(!showMappings)}
              >
                {showMappings ? 'Hide Card Mappings' : `Show Card Mappings (${Object.keys(presetForm.mappings_grouped).length} cards)`}
              </button>
            </div>

            {showMappings && (
              <MappingsEditor
                mappings={presetForm.mappings_grouped}
                onChange={(updated) =>
                  setPresetForm({ ...presetForm, mappings_grouped: updated })
                }
              />
            )}

            <div className="settings-tab__preset-form-actions">
              <button onClick={cancelEditPreset}>Cancel</button>
              <button
                className="settings-tab__save-btn"
                onClick={handleSavePreset}
                disabled={presetSaving}
              >
                {presetSaving ? 'Saving...' : 'Save Preset'}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
