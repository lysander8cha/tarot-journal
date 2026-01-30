import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTheme } from '../../context/ThemeContext';
import {
  getThemePresets,
  applyThemePreset,
  updateTheme,
  getDefaults,
  updateDefaults,
  createBackup,
  restoreBackup,
  getCacheStats,
  clearCache,
} from '../../api/settings';
import { getProfiles } from '../../api/profiles';
import { getCartomancyTypes, getDecks } from '../../api/decks';
import type { ThemeColors, Profile, Deck, CartomancyType } from '../../types';
import './SettingsTab.css';

const COLOR_LABELS: Record<string, string> = {
  bg_primary: 'Background',
  bg_secondary: 'Panels',
  bg_tertiary: 'Hover',
  bg_input: 'Inputs',
  accent: 'Accent',
  accent_hover: 'Accent Hover',
  accent_dim: 'Accent Dim',
  text_primary: 'Text',
  text_secondary: 'Text Secondary',
  text_dim: 'Text Dim',
  border: 'Borders',
  success: 'Success',
  warning: 'Warning',
  danger: 'Danger',
  card_slot: 'Card Slot',
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SettingsTab() {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();
  const [showCustomize, setShowCustomize] = useState(false);
  const [saving, setSaving] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [includeImages, setIncludeImages] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Local color editing state
  const [editColors, setEditColors] = useState<ThemeColors>({ ...theme.colors });

  useEffect(() => {
    setEditColors({ ...theme.colors });
  }, [theme.colors]);

  const { data: presets } = useQuery({
    queryKey: ['theme-presets'],
    queryFn: getThemePresets,
  });

  const { data: defaults } = useQuery({
    queryKey: ['settings-defaults'],
    queryFn: getDefaults,
  });

  const { data: profiles = [] } = useQuery<Profile[]>({
    queryKey: ['profiles'],
    queryFn: getProfiles,
  });

  const { data: cartomancyTypes = [] } = useQuery<CartomancyType[]>({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });

  const { data: decks = [] } = useQuery<Deck[]>({
    queryKey: ['decks'],
    queryFn: () => getDecks(),
  });

  const { data: cacheStats } = useQuery({
    queryKey: ['cache-stats'],
    queryFn: getCacheStats,
  });

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  const handlePreset = async (name: string) => {
    try {
      const result = await applyThemePreset(name);
      setTheme(result);
      showMsg(`Applied "${name}" theme`, 'success');
    } catch {
      showMsg('Failed to apply preset', 'error');
    }
  };

  const handleSaveCustomColors = async () => {
    setSaving(true);
    try {
      const result = await updateTheme({ colors: editColors });
      setTheme(result);
      setShowCustomize(false);
      showMsg('Custom colors saved', 'success');
    } catch {
      showMsg('Failed to save colors', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleColorChange = (key: string, value: string) => {
    setEditColors((prev) => ({ ...prev, [key]: value }));
    // Live preview
    setTheme({ ...theme, colors: { ...theme.colors, [key]: value } });
  };

  const handleDefaultChange = async (field: string, value: number | null | boolean) => {
    try {
      await updateDefaults({ [field]: value });
      queryClient.invalidateQueries({ queryKey: ['settings-defaults'] });
    } catch {
      showMsg('Failed to save default', 'error');
    }
  };

  const handleDefaultDeckChange = async (typeName: string, deckId: number | null) => {
    try {
      const updatedDecks = {
        ...(defaults?.default_decks || {}),
        [typeName]: deckId,
      };
      await updateDefaults({ default_decks: updatedDecks });
      queryClient.invalidateQueries({ queryKey: ['settings-defaults'] });
    } catch {
      showMsg('Failed to save default deck', 'error');
    }
  };

  // Helper to get decks that match a given cartomancy type
  const getDecksForType = (typeName: string): Deck[] => {
    return decks.filter(deck => {
      // Check multi-type array first
      if (deck.cartomancy_types && deck.cartomancy_types.length > 0) {
        return deck.cartomancy_types.some(t => t.name === typeName);
      }
      // Fall back to legacy single-type field
      return deck.cartomancy_type === typeName;
    });
  };

  const handleBackup = async () => {
    setBackingUp(true);
    try {
      const blob = await createBackup(includeImages);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tarot_backup_${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      queryClient.invalidateQueries({ queryKey: ['settings-defaults'] });
      showMsg('Backup created successfully', 'success');
    } catch {
      showMsg('Backup failed', 'error');
    } finally {
      setBackingUp(false);
    }
  };

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!window.confirm('Restore from backup? This will replace all current data. A safety backup will be created first.')) {
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    setRestoring(true);
    try {
      await restoreBackup(file);
      queryClient.invalidateQueries();
      showMsg('Backup restored successfully. Reload the page to see changes.', 'success');
    } catch {
      showMsg('Restore failed', 'error');
    } finally {
      setRestoring(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleClearCache = async () => {
    if (!window.confirm('Clear the thumbnail cache? Thumbnails will be regenerated as needed.')) return;
    try {
      await clearCache();
      queryClient.invalidateQueries({ queryKey: ['cache-stats'] });
      showMsg('Cache cleared', 'success');
    } catch {
      showMsg('Failed to clear cache', 'error');
    }
  };

  return (
    <div className="settings-tab">
      <div className="settings-tab__scroll">
        <h2 className="settings-tab__title">Settings</h2>

        {message && (
          <div className={`settings-tab__message settings-tab__message--${message.type}`}>
            {message.text}
          </div>
        )}

        {/* Theme Section */}
        <section className="settings-tab__section">
          <h3 className="settings-tab__section-title">Theme</h3>

          <div className="settings-tab__presets">
            {presets && Object.keys(presets).map((name) => (
              <button
                key={name}
                className="settings-tab__preset-btn"
                onClick={() => handlePreset(name)}
              >
                <span
                  className="settings-tab__preset-swatch"
                  style={{ background: presets[name].colors.accent }}
                />
                {name}
              </button>
            ))}
          </div>

          <button
            className="settings-tab__customize-btn"
            onClick={() => setShowCustomize(!showCustomize)}
          >
            {showCustomize ? 'Hide Custom Colors' : 'Customize Colors...'}
          </button>

          {showCustomize && (
            <div className="settings-tab__color-editor">
              <div className="settings-tab__color-grid">
                {Object.entries(COLOR_LABELS).map(([key, label]) => (
                  <div key={key} className="settings-tab__color-field">
                    <label className="settings-tab__color-label">{label}</label>
                    <div className="settings-tab__color-input-row">
                      <input
                        type="color"
                        value={editColors[key as keyof ThemeColors] || '#000000'}
                        onChange={(e) => handleColorChange(key, e.target.value)}
                      />
                      <span className="settings-tab__color-hex">
                        {editColors[key as keyof ThemeColors]}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="settings-tab__color-actions">
                <button onClick={() => { setEditColors({ ...theme.colors }); setShowCustomize(false); }}>
                  Cancel
                </button>
                <button
                  className="settings-tab__save-btn"
                  onClick={handleSaveCustomColors}
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Save Colors'}
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Defaults Section */}
        <section className="settings-tab__section">
          <h3 className="settings-tab__section-title">Defaults</h3>

          <div className="settings-tab__defaults-grid">
            <div className="settings-tab__field">
              <label className="settings-tab__label">Default Reader</label>
              <select
                value={defaults?.default_reader ?? ''}
                onChange={(e) => handleDefaultChange('default_reader', e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">None</option>
                {profiles
                  .filter((p) => !p.querent_only)
                  .map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
              </select>
            </div>

            <div className="settings-tab__field">
              <label className="settings-tab__label">Default Querent</label>
              <select
                value={defaults?.default_querent ?? ''}
                onChange={(e) => handleDefaultChange('default_querent', e.target.value ? Number(e.target.value) : null)}
                disabled={defaults?.default_querent_same_as_reader}
              >
                <option value="">None</option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div className="settings-tab__field settings-tab__field--checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={defaults?.default_querent_same_as_reader ?? false}
                  onChange={(e) => handleDefaultChange('default_querent_same_as_reader', e.target.checked)}
                />
                Querent same as reader
              </label>
            </div>
          </div>

          <h4 className="settings-tab__subsection-title">Default Decks</h4>
          <p className="settings-tab__hint">
            Select a default deck for each type. These will be auto-selected when creating journal entries.
          </p>
          <div className="settings-tab__defaults-grid">
            {cartomancyTypes.map((type) => {
              const typeDecks = getDecksForType(type.name);
              return (
                <div key={type.id} className="settings-tab__field">
                  <label className="settings-tab__label">{type.name}</label>
                  <select
                    value={defaults?.default_decks?.[type.name] ?? ''}
                    onChange={(e) => handleDefaultDeckChange(type.name, e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">None</option>
                    {typeDecks.map((deck) => (
                      <option key={deck.id} value={deck.id}>{deck.name}</option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        </section>

        {/* Backup & Restore Section */}
        <section className="settings-tab__section">
          <h3 className="settings-tab__section-title">Backup & Restore</h3>

          {defaults?.last_backup_time && (
            <p className="settings-tab__last-backup">
              Last backup: {new Date(defaults.last_backup_time).toLocaleString()}
            </p>
          )}

          <div className="settings-tab__backup-row">
            <label className="settings-tab__checkbox-label">
              <input
                type="checkbox"
                checked={includeImages}
                onChange={(e) => setIncludeImages(e.target.checked)}
              />
              Include card images
            </label>
            <button
              className="settings-tab__backup-btn"
              onClick={handleBackup}
              disabled={backingUp}
            >
              {backingUp ? 'Creating...' : 'Create Backup'}
            </button>
          </div>

          <div className="settings-tab__restore-row">
            <button
              className="settings-tab__restore-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={restoring}
            >
              {restoring ? 'Restoring...' : 'Restore from Backup'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleRestore}
              style={{ display: 'none' }}
            />
          </div>
        </section>

        {/* Cache Section */}
        <section className="settings-tab__section">
          <h3 className="settings-tab__section-title">Thumbnail Cache</h3>
          {cacheStats && (
            <p className="settings-tab__cache-info">
              {cacheStats.count} thumbnails ({formatBytes(cacheStats.size_bytes)})
            </p>
          )}
          <button className="settings-tab__clear-cache-btn" onClick={handleClearCache}>
            Clear Cache
          </button>
        </section>
      </div>
    </div>
  );
}
