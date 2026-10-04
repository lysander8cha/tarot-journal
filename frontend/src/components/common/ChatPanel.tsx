/**
 * Reusable assistant chat: message log + input row. Purely
 * presentational — the parent owns the conversation state and calls
 * the model; this renders whatever it's given and reports sends.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import './ChatPanel.css';

export interface ChatDisplayMessage {
  role: 'user' | 'assistant' | 'error' | 'note';
  text: string;
}

interface ChatPanelProps {
  messages: ChatDisplayMessage[];
  busy: boolean;
  onSend: (text: string) => void;
  placeholder?: string;
  /** Shown in the empty log before any messages arrive. */
  emptyHint?: string;
  busyLabel?: string;
  /** Keep the input live while busy (the parent queues the message). */
  allowSendWhileBusy?: boolean;
  /** Placeholder shown while busy, when sending is still allowed. */
  busyPlaceholder?: string;
  /** Extras rendered at the end of the log (e.g. a resume button). */
  children?: ReactNode;
}

export default function ChatPanel({
  messages,
  busy,
  onSend,
  placeholder = 'Type a message… (Enter to send, Shift+Enter for a new line)',
  emptyHint,
  busyLabel = 'Working…',
  allowSendWhileBusy = false,
  busyPlaceholder,
  children,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const locked = busy && !allowSendWhileBusy;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const send = () => {
    const text = input.trim();
    if (!text || locked) return;
    setInput('');
    onSend(text);
  };

  return (
    <div className="chat-panel">
      <div className="chat-panel__log">
        {messages.length === 0 && !busy && emptyHint && (
          <p className="chat-panel__empty">{emptyHint}</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-panel__msg chat-panel__msg--${m.role}`}>
            {m.text}
          </div>
        ))}
        {busy && (
          <div className="chat-panel__msg chat-panel__msg--assistant chat-panel__msg--busy">
            {busyLabel}
          </div>
        )}
        {children}
        <div ref={endRef} />
      </div>
      <div className="chat-panel__input">
        <textarea
          value={input}
          placeholder={busy && busyPlaceholder ? busyPlaceholder : placeholder}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          rows={2}
          disabled={locked}
        />
        <button onClick={send} disabled={locked || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
