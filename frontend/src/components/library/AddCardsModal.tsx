import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { scanNewCards, addCardsToDeck } from '../../api/importExport';
import { useToast } from '../../context/ToastContext';
import Modal, { ModalCancelButton } from '../common/Modal';
import './AddCardsModal.css';

interface AddCardsModalProps {
  deckId: number;
  deckName: string;
  onClose: () => void;
  onImported: () => void;
}

type Step = 'select' | 'preview' | 'importing' | 'done';

export default function AddCardsModal({ deckId, deckName, onClose, onImported }: AddCardsModalProps) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [folder, setFolder] = useState('');
  const [step, setStep] = useState<Step>('select');
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');
  const [previewCards, setPreviewCards] = useState<{ filename: string; name: string }[]>([]);
  const [existingCount, setExistingCount] = useState(0);
  const [result, setResult] = useState<{ cards_added: number } | null>(null);

  const handleBrowse = async () => {
    if (window.electronAPI?.openDirectory) {
      const selected = await window.electronAPI.openDirectory({
        title: 'Select Folder with Card Images',
      });
      if (selected) setFolder(selected);
    }
  };

  const handleScan = async () => {
    if (!folder.trim()) {
      setError('Please select a folder');
      return;
    }
    setError('');
    setScanning(true);
    try {
      const res = await scanNewCards(deckId, folder);
      setPreviewCards(res.cards);
      setExistingCount(res.existing_count);
      if (res.count === 0) {
        setError('No new images found. Images already in the deck are skipped.');
      } else {
        setStep('preview');
      }
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
        : null;
      setError(msg || 'Failed to scan folder');
    } finally {
      setScanning(false);
    }
  };

  const handleImport = async () => {
    setError('');
    setStep('importing');
    try {
      const res = await addCardsToDeck(deckId, folder);
      setResult(res);
      setStep('done');
      queryClient.invalidateQueries({ queryKey: ['cards', deckId] });
      queryClient.invalidateQueries({ queryKey: ['decks'] });
      onImported();
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
        : null;
      showToast(msg || 'Failed to import cards.');
      setStep('preview');
    }
  };

  const isElectron = typeof window !== 'undefined' && window.electronAPI?.isElectron;
  const isDirty = folder.trim().length > 0 && step !== 'done';

  return (
    <Modal open={true} onClose={onClose} title={`Add Cards to ${deckName}`} width={550} isDirty={isDirty}>
      <div className="add-cards">
        {error && <div className="add-cards__error">{error}</div>}

        {step === 'select' && (
          <>
            <p className="add-cards__hint">
              Select a folder containing card images. Images already in the deck will be skipped.
            </p>
            <div className="add-cards__folder-row">
              <input
                type="text"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder="/path/to/card/images"
                className="add-cards__folder-input"
              />
              {isElectron && (
                <button className="add-cards__browse-btn" onClick={handleBrowse}>
                  Browse...
                </button>
              )}
            </div>
            <div className="add-cards__footer">
              <ModalCancelButton>Cancel</ModalCancelButton>
              <button
                className="add-cards__primary-btn"
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
            <p className="add-cards__hint">
              Found <strong>{previewCards.length}</strong> new image{previewCards.length !== 1 ? 's' : ''} to add
              {existingCount > 0 && ` (${existingCount} existing cards in deck)`}.
            </p>
            <div className="add-cards__preview-list">
              {previewCards.map((c, i) => (
                <div key={i} className="add-cards__preview-row">
                  <span className="add-cards__preview-num">{i + 1}</span>
                  <span className="add-cards__preview-filename">{c.filename}</span>
                  <span className="add-cards__preview-name">{c.name}</span>
                </div>
              ))}
            </div>
            <div className="add-cards__footer">
              <button onClick={() => setStep('select')}>Back</button>
              <button className="add-cards__primary-btn" onClick={handleImport}>
                Import {previewCards.length} Card{previewCards.length !== 1 ? 's' : ''}
              </button>
            </div>
          </>
        )}

        {step === 'importing' && (
          <div className="add-cards__status">Importing cards...</div>
        )}

        {step === 'done' && result && (
          <>
            <div className="add-cards__status add-cards__status--success">
              Added {result.cards_added} card{result.cards_added !== 1 ? 's' : ''} to {deckName}.
            </div>
            <div className="add-cards__footer">
              <button className="add-cards__primary-btn" onClick={onClose}>Done</button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
