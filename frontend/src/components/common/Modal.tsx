import { useEffect, useRef, useState, type ReactNode } from 'react';
import './Modal.css';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  width?: number;
  children: ReactNode;
  /** When true, shows a confirmation dialog before closing */
  isDirty?: boolean;
  /** Custom message for the confirmation dialog */
  confirmMessage?: string;
}

export default function Modal({
  open,
  onClose,
  title,
  width = 700,
  children,
  isDirty = false,
  confirmMessage = 'You have unsaved changes. Are you sure you want to close?',
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // Reset confirm dialog when modal closes
  useEffect(() => {
    if (!open) setShowConfirm(false);
  }, [open]);

  const attemptClose = () => {
    if (isDirty) {
      setShowConfirm(true);
    } else {
      onClose();
    }
  };

  const confirmClose = () => {
    setShowConfirm(false);
    onClose();
  };

  const cancelClose = () => {
    setShowConfirm(false);
  };

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showConfirm) {
          // If confirm dialog is open, Escape cancels it
          cancelClose();
        } else {
          attemptClose();
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose, isDirty, showConfirm]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      ref={overlayRef}
      onMouseDown={(e) => {
        // Only close if mousedown directly on overlay (not dragged from content)
        if (e.target === overlayRef.current) attemptClose();
      }}
    >
      <div className="modal-content" style={{ maxWidth: width }}>
        {title && (
          <div className="modal-header">
            <h2 className="modal-title">{title}</h2>
            <button className="modal-close" onClick={attemptClose}>&times;</button>
          </div>
        )}
        <div className="modal-body">
          {children}
        </div>
      </div>

      {/* Confirmation dialog */}
      {showConfirm && (
        <div className="modal-confirm-overlay" onClick={cancelClose}>
          <div className="modal-confirm" onClick={(e) => e.stopPropagation()}>
            <p className="modal-confirm__message">{confirmMessage}</p>
            <div className="modal-confirm__buttons">
              <button onClick={cancelClose}>Keep Editing</button>
              <button className="danger" onClick={confirmClose}>Discard Changes</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
