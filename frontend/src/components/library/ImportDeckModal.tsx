import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCartomancyTypes } from '../../api/decks';
import {
  getImportPresets,
  getPresetInfo,
  scanFolder,
  importFromFolder,
  type PreviewCard,
} from '../../api/importExport';
import {
  COURT_PRESETS,
  ARCHETYPE_MAPPING_OPTIONS,
  DEFAULT_SUIT_NAMES,
  DEFAULT_COURT_NAMES,
  TAROT_SUITS,
  PLAYING_SUITS,
} from '../../constants/importPresets';
import Modal from '../common/Modal';
import './ImportDeckModal.css';

// Extend window type for Electron API
declare global {
  interface Window {
    electronAPI?: {
      openDirectory: (options?: { title?: string }) => Promise<string | null>;
      isElectron: boolean;
    };
  }
}

interface ImportDeckModalProps {
  onClose: () => void;
  onImported: (deckId: number) => void;
}

type Step = 'configure' | 'preview' | 'importing' | 'done';

export default function ImportDeckModal({ onClose, onImported }: ImportDeckModalProps) {
  const queryClient = useQueryClient();

  const { data: types = [] } = useQuery({
    queryKey: ['cartomancy-types'],
    queryFn: getCartomancyTypes,
  });

  const { data: presets = [] } = useQuery({
    queryKey: ['import-presets'],
    queryFn: getImportPresets,
  });

  // Basic configuration
  const [folder, setFolder] = useState('');
  const [deckName, setDeckName] = useState('');
  const [typeId, setTypeId] = useState<number>(0);
  const [preset, setPreset] = useState('');
  const [error, setError] = useState('');

  // Deck type detection (from preset)
  const [deckType, setDeckType] = useState<string>('Tarot');

  // Suit name customization
  const [suitNames, setSuitNames] = useState<Record<string, string>>(
    DEFAULT_SUIT_NAMES['Tarot']
  );

  // Court card settings (Tarot only)
  const [courtPreset, setCourtPreset] = useState<string>('RWS (Page/Knight/Queen/King)');
  const [customCourtNames, setCustomCourtNames] = useState<Record<string, string>>(
    DEFAULT_COURT_NAMES
  );
  const [archetypeMapping, setArchetypeMapping] = useState<string>(
    ARCHETYPE_MAPPING_OPTIONS[0]
  );

  // Step management
  const [step, setStep] = useState<Step>('configure');
  const [previewCards, setPreviewCards] = useState<PreviewCard[]>([]);
  const [scanning, setScanning] = useState(false);

  // Result
  const [result, setResult] = useState<{ deck_id: number; cards_imported: number } | null>(null);

  // Default type to first available
  useEffect(() => {
    if (typeId === 0 && types.length > 0) {
      setTypeId(types[0].id);
    }
  }, [typeId, types]);

  // Get current suit keys based on deck type
  const getSuitKeys = useCallback(() => {
    if (deckType === 'Lenormand' || deckType === 'Playing Cards') {
      return PLAYING_SUITS;
    }
    return TAROT_SUITS;
  }, [deckType]);

  // Get effective court names based on preset selection
  const getEffectiveCourtNames = useCallback(() => {
    const presetValues = COURT_PRESETS[courtPreset];
    if (presetValues === null) {
      // Custom mode - use manual entries
      return customCourtNames;
    }
    return presetValues;
  }, [courtPreset, customCourtNames]);

  // Handle preset change - fetch preset info and update UI accordingly
  useEffect(() => {
    if (!preset) {
      setDeckType('Oracle');
      setSuitNames(DEFAULT_SUIT_NAMES['Oracle']);
      return;
    }

    getPresetInfo(preset).then((info) => {
      if (info) {
        const newType = info.type || 'Oracle';
        setDeckType(newType);

        // Update suit names from preset or use defaults for new type
        if (info.suit_names) {
          setSuitNames(info.suit_names);
        } else {
          setSuitNames(DEFAULT_SUIT_NAMES[newType] || DEFAULT_SUIT_NAMES['Oracle']);
        }

        // Update cartomancy type dropdown to match preset
        const matchingType = types.find((t) => t.name === newType);
        if (matchingType) {
          setTypeId(matchingType.id);
        }
      }
    });
  }, [preset, types]);

  // Handle folder browse button
  const handleBrowse = async () => {
    if (window.electronAPI?.openDirectory) {
      const selectedFolder = await window.electronAPI.openDirectory({
        title: 'Select Folder with Card Images',
      });
      if (selectedFolder) {
        setFolder(selectedFolder);
        // Auto-populate deck name from folder name
        if (!deckName) {
          const parts = selectedFolder.replace(/\/$/, '').split('/');
          setDeckName(parts[parts.length - 1]);
        }
      }
    }
  };

  const handleScan = async () => {
    if (!folder.trim()) {
      setError('Please select or enter a folder path');
      return;
    }
    setError('');
    setScanning(true);

    try {
      const res = await scanFolder({
        folder,
        preset_name: preset,
        custom_suit_names: suitNames,
        custom_court_names: deckType === 'Tarot' ? getEffectiveCourtNames() : undefined,
        archetype_mapping: deckType === 'Tarot' ? archetypeMapping : undefined,
      });
      setPreviewCards(res.cards);
      if (!deckName) {
        // Default deck name to folder name
        const parts = folder.replace(/\/$/, '').split('/');
        setDeckName(parts[parts.length - 1]);
      }
      setStep('preview');
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
          : null;
      setError(errorMessage || 'Failed to scan folder');
    } finally {
      setScanning(false);
    }
  };

  const handleImport = async () => {
    if (!deckName.trim()) {
      setError('Deck name is required');
      return;
    }
    setError('');
    setStep('importing');

    try {
      const res = await importFromFolder({
        folder,
        deck_name: deckName,
        cartomancy_type_id: typeId,
        preset_name: preset,
        custom_suit_names: suitNames,
        custom_court_names: deckType === 'Tarot' ? getEffectiveCourtNames() : undefined,
        archetype_mapping: deckType === 'Tarot' ? archetypeMapping : undefined,
      });
      setResult(res);
      setStep('done');
      queryClient.invalidateQueries({ queryKey: ['decks'] });
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
          : null;
      setError(errorMessage || 'Import failed');
      setStep('preview');
    }
  };

  const handleSuitNameChange = (key: string, value: string) => {
    setSuitNames((prev) => ({ ...prev, [key]: value }));
  };

  const handleCourtNameChange = (key: string, value: string) => {
    setCustomCourtNames((prev) => ({ ...prev, [key]: value }));
  };

  const handleCourtPresetChange = (value: string) => {
    setCourtPreset(value);
    // If selecting a preset, update the custom fields to match (for display consistency)
    const presetValues = COURT_PRESETS[value];
    if (presetValues) {
      setCustomCourtNames(presetValues);
    }
  };

  const isElectron = typeof window !== 'undefined' && window.electronAPI?.isElectron;
  const isTarot = deckType === 'Tarot';
  const showCustomCourtFields = courtPreset === 'Custom...';
  const suitKeys = getSuitKeys();

  return (
    <Modal open={true} onClose={onClose} width={650}>
      <div className="import-deck">
        <h2 className="import-deck__title">Import Deck from Folder</h2>

        {error && <div className="import-deck__error">{error}</div>}

        {step === 'configure' && (
          <>
            <div className="import-deck__form">
              {/* Folder path with browse button */}
              <div className="import-deck__field">
                <label className="import-deck__label">Image Folder Path</label>
                <div className="import-deck__folder-row">
                  <input
                    type="text"
                    value={folder}
                    onChange={(e) => setFolder(e.target.value)}
                    placeholder="/path/to/card/images"
                    className="import-deck__folder-input"
                  />
                  {isElectron && (
                    <button
                      type="button"
                      className="import-deck__browse-btn"
                      onClick={handleBrowse}
                    >
                      Browse...
                    </button>
                  )}
                </div>
              </div>

              {/* Deck name */}
              <div className="import-deck__field">
                <label className="import-deck__label">Deck Name</label>
                <input
                  type="text"
                  value={deckName}
                  onChange={(e) => setDeckName(e.target.value)}
                  placeholder="Will default to folder name"
                />
              </div>

              {/* Type and preset row */}
              <div className="import-deck__row">
                <div className="import-deck__field" style={{ flex: 1 }}>
                  <label className="import-deck__label">Cartomancy Type</label>
                  <select
                    value={typeId}
                    onChange={(e) => setTypeId(parseInt(e.target.value))}
                  >
                    {types.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="import-deck__field" style={{ flex: 1 }}>
                  <label className="import-deck__label">Import Preset</label>
                  <select value={preset} onChange={(e) => setPreset(e.target.value)}>
                    <option value="">None (use filenames)</option>
                    {presets.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Suit Names Section */}
              <div className="import-deck__section">
                <div className="import-deck__section-title">Suit Names</div>
                <div className="import-deck__suit-grid">
                  {suitKeys.map((key) => (
                    <div key={key} className="import-deck__suit-field">
                      <label className="import-deck__suit-label">
                        {key.charAt(0).toUpperCase() + key.slice(1)}:
                      </label>
                      <input
                        type="text"
                        value={suitNames[key] || key.charAt(0).toUpperCase() + key.slice(1)}
                        onChange={(e) => handleSuitNameChange(key, e.target.value)}
                        className="import-deck__suit-input"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Court Cards Section (Tarot only) */}
              {isTarot && (
                <div className="import-deck__section">
                  <div className="import-deck__section-title">Court Cards</div>

                  <div className="import-deck__court-row">
                    <div className="import-deck__field" style={{ flex: 1 }}>
                      <label className="import-deck__label">Court Style</label>
                      <select
                        value={courtPreset}
                        onChange={(e) => handleCourtPresetChange(e.target.value)}
                      >
                        {Object.keys(COURT_PRESETS).map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="import-deck__field" style={{ flex: 1 }}>
                      <label className="import-deck__label">Archetype Mapping</label>
                      <select
                        value={archetypeMapping}
                        onChange={(e) => setArchetypeMapping(e.target.value)}
                      >
                        {ARCHETYPE_MAPPING_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Custom court name fields */}
                  {showCustomCourtFields && (
                    <div className="import-deck__suit-grid">
                      {['page', 'knight', 'queen', 'king'].map((key) => (
                        <div key={key} className="import-deck__suit-field">
                          <label className="import-deck__suit-label">
                            {key.charAt(0).toUpperCase() + key.slice(1)}:
                          </label>
                          <input
                            type="text"
                            value={customCourtNames[key] || ''}
                            onChange={(e) => handleCourtNameChange(key, e.target.value)}
                            className="import-deck__suit-input"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="import-deck__footer">
              <button onClick={onClose}>Cancel</button>
              <button
                className="import-deck__primary-btn"
                onClick={handleScan}
                disabled={scanning || !folder.trim()}
              >
                {scanning ? 'Scanning...' : 'Scan Folder'}
              </button>
            </div>
          </>
        )}

        {step === 'preview' && (
          <>
            <div className="import-deck__preview">
              <p className="import-deck__preview-count">
                Found {previewCards.length} cards in folder
              </p>
              <div className="import-deck__preview-list">
                <div className="import-deck__preview-header">
                  <span>#</span>
                  <span>Filename</span>
                  <span>Card Name</span>
                </div>
                {previewCards.map((c, i) => (
                  <div key={i} className="import-deck__preview-row">
                    <span>{c.sort_order}</span>
                    <span className="import-deck__preview-filename">{c.filename}</span>
                    <span>{c.name}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="import-deck__footer">
              <button onClick={() => setStep('configure')}>Back</button>
              <button
                className="import-deck__primary-btn"
                onClick={handleImport}
                disabled={!deckName.trim()}
              >
                Import {previewCards.length} Cards
              </button>
            </div>
          </>
        )}

        {step === 'importing' && (
          <div className="import-deck__status">Importing cards...</div>
        )}

        {step === 'done' && result && (
          <>
            <div className="import-deck__status import-deck__status--success">
              Successfully imported {result.cards_imported} cards!
            </div>
            <div className="import-deck__footer">
              <button
                className="import-deck__primary-btn"
                onClick={() => {
                  onImported(result.deck_id);
                  onClose();
                }}
              >
                View Deck
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
