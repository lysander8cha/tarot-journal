import { useState, useRef, useCallback, useMemo } from 'react';
import type { SpreadPosition, DeckSlot } from '../../types';
import './SpreadDesigner.css';

// Minimum canvas dimensions (used when empty or for small spreads)
const MIN_CANVAS_W = 620;
const MIN_CANVAS_H = 460;
const GRID_SIZE = 20;
const DEFAULT_W = 80;
const DEFAULT_H = 120;
const HANDLE_SIZE = 16;
const CANVAS_PADDING = 20; // Padding around content

interface SpreadDesignerProps {
  positions: SpreadPosition[];
  onChange: (positions: SpreadPosition[]) => void;
  selectedIndex: number | null;
  onSelectIndex: (index: number | null) => void;
  deckSlots: DeckSlot[];
}

export default function SpreadDesigner({
  positions,
  onChange,
  selectedIndex,
  onSelectIndex,
  deckSlots,
}: SpreadDesignerProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [gridEnabled, setGridEnabled] = useState(true);
  const [showLabelsOnPositions, setShowLabelsOnPositions] = useState(false);
  const [dragging, setDragging] = useState<{
    index: number;
    startMouseX: number;
    startMouseY: number;
    startPosX: number;
    startPosY: number;
  } | null>(null);
  const [resizing, setResizing] = useState<{
    index: number;
    startClientX: number;  // Screen coordinates (stable during resize)
    startClientY: number;
    startW: number;
    startH: number;
    scaleX: number;  // Locked scale factor at start of resize
    scaleY: number;
  } | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    index: number;
  } | null>(null);
  const [showSlotMenu, setShowSlotMenu] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editLabel, setEditLabel] = useState('');
  const [editKey, setEditKey] = useState('');

  // Calculate dynamic canvas dimensions based on position bounding box
  const canvasDimensions = useMemo(() => {
    if (positions.length === 0) {
      return { width: MIN_CANVAS_W, height: MIN_CANVAS_H };
    }
    // Find the bounding box of all positions
    const maxX = Math.max(...positions.map(p => (p.x || 0) + (p.width || DEFAULT_W)));
    const maxY = Math.max(...positions.map(p => (p.y || 0) + (p.height || DEFAULT_H)));
    // Use the larger of content bounds + padding or minimum dimensions
    return {
      width: Math.max(MIN_CANVAS_W, maxX + CANVAS_PADDING),
      height: Math.max(MIN_CANVAS_H, maxY + CANVAS_PADDING),
    };
  }, [positions]);

  const snap = useCallback(
    (val: number) => (gridEnabled ? Math.round(val / GRID_SIZE) * GRID_SIZE : Math.round(val)),
    [gridEnabled],
  );

  // Convert screen coordinates to viewBox (logical) coordinates
  const getSVGPoint = useCallback(
    (e: React.MouseEvent) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      // Calculate scale factor from rendered size to viewBox size
      const scaleX = canvasDimensions.width / rect.width;
      const scaleY = canvasDimensions.height / rect.height;
      return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
      };
    },
    [canvasDimensions],
  );

  const handleAddPosition = () => {
    const cx = snap(canvasDimensions.width / 2 - DEFAULT_W / 2);
    const cy = snap(canvasDimensions.height / 2 - DEFAULT_H / 2);
    const newIndex = positions.length;
    const defaultLabel = `Position ${newIndex + 1}`;
    const defaultKey = String(newIndex + 1);
    onChange([
      ...positions,
      { x: cx, y: cy, width: DEFAULT_W, height: DEFAULT_H, label: defaultLabel, key: defaultKey },
    ]);
    onSelectIndex(newIndex);
    // Open context menu for the new position so user can edit
    // Use a small delay to ensure the position is rendered
    setTimeout(() => {
      const svg = svgRef.current;
      if (svg) {
        const rect = svg.getBoundingClientRect();
        setContextMenu({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
          index: newIndex,
        });
        setEditMode(true);
        setEditLabel(defaultLabel);
        setEditKey(defaultKey);
      }
    }, 0);
  };

  const handleClearAll = () => {
    if (positions.length === 0) return;
    if (!window.confirm('Clear all positions?')) return;
    onChange([]);
    onSelectIndex(null);
  };

  // ── Mouse handlers ──

  const handlePositionMouseDown = (e: React.MouseEvent, index: number) => {
    if (e.button !== 0) return; // left click only
    e.stopPropagation();
    const pt = getSVGPoint(e);
    const pos = positions[index];
    setDragging({
      index,
      startMouseX: pt.x,
      startMouseY: pt.y,
      startPosX: pos.x,
      startPosY: pos.y,
    });
    onSelectIndex(index);
    setContextMenu(null);
  };

  const handleResizeMouseDown = (e: React.MouseEvent, index: number) => {
    if (e.button !== 0) return; // left click only
    e.stopPropagation();
    e.preventDefault();
    const pos = positions[index];
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    // Store screen coordinates and lock scale factors at start of resize
    // This prevents jumpy behavior when canvas dimensions change during drag
    setResizing({
      index,
      startClientX: e.clientX,
      startClientY: e.clientY,
      startW: pos.width,
      startH: pos.height,
      scaleX: canvasDimensions.width / rect.width,
      scaleY: canvasDimensions.height / rect.height,
    });
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragging) {
        const pt = getSVGPoint(e);
        const dx = pt.x - dragging.startMouseX;
        const dy = pt.y - dragging.startMouseY;
        let newX = snap(dragging.startPosX + dx);
        let newY = snap(dragging.startPosY + dy);
        // Only prevent negative coordinates; canvas will grow to fit
        newX = Math.max(0, newX);
        newY = Math.max(0, newY);
        const updated = [...positions];
        updated[dragging.index] = { ...updated[dragging.index], x: newX, y: newY };
        onChange(updated);
      }

      if (resizing) {
        // Use locked scale factors from start of resize to avoid jumpy behavior
        // when canvas dimensions change during drag
        const dx = (e.clientX - resizing.startClientX) * resizing.scaleX;
        const dy = (e.clientY - resizing.startClientY) * resizing.scaleY;
        const newW = snap(Math.max(40, resizing.startW + dx));
        const newH = snap(Math.max(40, resizing.startH + dy));
        // No upper limit on size; canvas will grow to fit
        const updated = [...positions];
        updated[resizing.index] = { ...updated[resizing.index], width: newW, height: newH };
        onChange(updated);
      }
    },
    [dragging, resizing, positions, onChange, getSVGPoint, snap],
  );

  const handleMouseUp = useCallback(() => {
    setDragging(null);
    setResizing(null);
  }, []);

  const handleCanvasClick = () => {
    onSelectIndex(null);
    setContextMenu(null);
  };

  // ── Context menu ──

  const handleContextMenu = (e: React.MouseEvent, index: number) => {
    e.preventDefault();
    e.stopPropagation();
    onSelectIndex(index);
    setContextMenu({ x: e.clientX, y: e.clientY, index });
  };

  const handleEditPosition = () => {
    if (contextMenu === null) return;
    const pos = positions[contextMenu.index];
    setEditLabel(pos.label || '');
    setEditKey(pos.key || String(contextMenu.index + 1));
    setEditMode(true);
  };

  const handleSaveEdit = () => {
    if (contextMenu === null) return;
    const updated = [...positions];
    updated[contextMenu.index] = {
      ...updated[contextMenu.index],
      label: editLabel,
      key: editKey || undefined,
    };
    onChange(updated);
    setEditMode(false);
    setContextMenu(null);
  };

  const handleCancelEdit = () => {
    setEditMode(false);
    setContextMenu(null);
  };

  const handleRotatePosition = () => {
    if (contextMenu === null) return;
    const pos = positions[contextMenu.index];
    const updated = [...positions];
    updated[contextMenu.index] = {
      ...updated[contextMenu.index],
      width: pos.height,
      height: pos.width,
      rotated: !pos.rotated,
    };
    onChange(updated);
    setContextMenu(null);
  };

  const handleDeletePosition = () => {
    if (contextMenu === null) return;
    const updated = positions.filter((_, i) => i !== contextMenu.index);
    onChange(updated);
    onSelectIndex(null);
    setContextMenu(null);
  };

  const handleSetDeckSlot = (slotKey: string | null) => {
    if (contextMenu === null) return;
    const updated = [...positions];
    updated[contextMenu.index] = {
      ...updated[contextMenu.index],
      deck_slot: slotKey || undefined,
    };
    onChange(updated);
    setShowSlotMenu(false);
    setContextMenu(null);
  };

  // ── Grid lines ──

  const gridLines = [];
  if (gridEnabled) {
    for (let x = GRID_SIZE; x < canvasDimensions.width; x += GRID_SIZE) {
      gridLines.push(
        <line key={`gx-${x}`} x1={x} y1={0} x2={x} y2={canvasDimensions.height} className="designer__grid-line" />,
      );
    }
    for (let y = GRID_SIZE; y < canvasDimensions.height; y += GRID_SIZE) {
      gridLines.push(
        <line key={`gy-${y}`} x1={0} y1={y} x2={canvasDimensions.width} y2={y} className="designer__grid-line" />,
      );
    }
  }

  return (
    <div className="designer">
      <div className="designer__toolbar">
        <button onClick={handleAddPosition}>+ Add Position</button>
        <button onClick={handleClearAll} disabled={positions.length === 0}>Clear All</button>
        <label className="designer__grid-toggle">
          <input
            type="checkbox"
            checked={gridEnabled}
            onChange={(e) => setGridEnabled(e.target.checked)}
          />
          <span>Snap to Grid</span>
        </label>
        <label className="designer__grid-toggle">
          <input
            type="checkbox"
            checked={showLabelsOnPositions}
            onChange={(e) => setShowLabelsOnPositions(e.target.checked)}
          />
          <span>Show Labels</span>
        </label>
      </div>

      <div className="designer__canvas-wrapper">
        <svg
          ref={svgRef}
          className="designer__canvas"
          viewBox={`0 0 ${canvasDimensions.width} ${canvasDimensions.height}`}
          style={{ aspectRatio: `${canvasDimensions.width} / ${canvasDimensions.height}` }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={handleCanvasClick}
        >
          {/* Background */}
          <rect width={canvasDimensions.width} height={canvasDimensions.height} className="designer__bg" />

          {/* Grid */}
          {gridLines}

          {/* Positions */}
          {positions.map((pos, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <g key={idx}>
                {/* Card rectangle */}
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={pos.width}
                  height={pos.height}
                  className={`designer__position ${isSelected ? 'designer__position--selected' : ''}`}
                  onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                  onContextMenu={(e) => handleContextMenu(e, idx)}
                  style={{ cursor: dragging ? 'grabbing' : 'grab' }}
                />

                {/* Key badge (top-left corner) */}
                <circle
                  cx={pos.x + 12}
                  cy={pos.y + 12}
                  r={9}
                  className="designer__key-bg"
                  onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                />
                <text
                  x={pos.x + 12}
                  y={pos.y + 16}
                  className="designer__key-text"
                  onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                >
                  {pos.key || idx + 1}
                </text>

                {/* Label (center) - only shown when toggle is enabled */}
                {showLabelsOnPositions && (
                  <text
                    x={pos.x + pos.width / 2}
                    y={pos.y + pos.height / 2 + 4}
                    className="designer__label-text"
                    onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                  >
                    {pos.label}
                  </text>
                )}

                {/* Rotated indicator */}
                {pos.rotated && (
                  <text
                    x={pos.x + pos.width - 14}
                    y={pos.y + 15}
                    className="designer__rotated-icon"
                    onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                  >
                    ↺
                  </text>
                )}

                {/* Deck slot indicator (bottom) - only show if multiple slots */}
                {deckSlots.length > 1 && (
                  <text
                    x={pos.x + pos.width / 2}
                    y={pos.y + pos.height - 6}
                    className="designer__slot-text"
                    onMouseDown={(e) => handlePositionMouseDown(e, idx)}
                  >
                    {pos.deck_slot || deckSlots[0]?.key || 'A'}
                  </text>
                )}

                {/* Resize handle - rendered INSIDE each position's group, AFTER other elements
                    so it's on top in z-order. Visible on hover via CSS. */}
                <rect
                  x={pos.x + pos.width - HANDLE_SIZE}
                  y={pos.y + pos.height - HANDLE_SIZE}
                  width={HANDLE_SIZE}
                  height={HANDLE_SIZE}
                  className={`designer__resize-handle ${isSelected ? 'designer__resize-handle--visible' : ''}`}
                  onMouseDown={(e) => handleResizeMouseDown(e, idx)}
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Context menu */}
      {contextMenu && (
        <>
          <div className="designer__menu-overlay" onClick={() => { setContextMenu(null); setShowSlotMenu(false); setEditMode(false); }} />
          <div
            className="designer__context-menu"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            {editMode ? (
              <div className="designer__edit-form">
                <div className="designer__edit-field">
                  <label>Label:</label>
                  <input
                    type="text"
                    value={editLabel}
                    onChange={(e) => setEditLabel(e.target.value)}
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveEdit();
                      if (e.key === 'Escape') handleCancelEdit();
                    }}
                  />
                </div>
                <div className="designer__edit-field">
                  <label>Key:</label>
                  <input
                    type="text"
                    value={editKey}
                    onChange={(e) => setEditKey(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveEdit();
                      if (e.key === 'Escape') handleCancelEdit();
                    }}
                  />
                </div>
                <div className="designer__edit-buttons">
                  <button onClick={handleSaveEdit}>Save</button>
                  <button onClick={handleCancelEdit}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                <button onClick={handleEditPosition}>Edit Label / Key</button>
                <button onClick={handleRotatePosition}>
                  {positions[contextMenu.index]?.rotated ? 'Unrotate' : 'Rotate 90°'}
                </button>
                {/* Only show deck slot option if there are multiple slots */}
                {deckSlots.length > 1 && (
                  <>
                    <button onClick={() => setShowSlotMenu(!showSlotMenu)}>
                      Deck Slot: {positions[contextMenu.index]?.deck_slot || deckSlots[0]?.key || 'A'} ▸
                    </button>
                    {showSlotMenu && (
                      <div className="designer__submenu">
                        {deckSlots.map((slot) => (
                          <button key={slot.key} onClick={() => handleSetDeckSlot(slot.key)}>
                            {slot.key}: {slot.label || slot.cartomancy_type}
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
                <button onClick={handleDeletePosition} className="designer__menu-danger">Delete</button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
