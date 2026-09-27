import { useQuery } from '@tanstack/react-query';
import { getSpread } from '../../api/spreads';
import { cardPreviewUrl } from '../../api/images';
import type { CardUsed, EntryReadingParsed, Spread, SpreadPosition } from '../../types';
import type { BirthCardTag } from './QuerentBirthCards';
import './SpreadDisplay.css';

interface SpreadDisplayProps {
  reading: EntryReadingParsed;
  onCardDoubleClick?: (cardId: number) => void;
  /** "Indicate Birth Cards": lowercase Tarot archetype name -> tag
   *  (label like "Soul" / "Anna: Year Card 2026", plus which system
   *  flagged it, for the color coding). Only Tarot cards match. */
  birthLabels?: Map<string, BirthCardTag>;
}

/** The querent birth-card label for a card, if highlighting is on and
 *  this is a Tarot card whose archetype is one of the birth cards. */
function birthLabelFor(
  card: CardUsed | undefined,
  birthLabels?: Map<string, BirthCardTag>,
): BirthCardTag | undefined {
  if (!card || !birthLabels || card.cartomancy_type !== 'Tarot') return undefined;
  return birthLabels.get((card.archetype || '').toLowerCase());
}

/** Inline CSS custom props carrying a tag's colors into the
 *  highlight styles; a second distinct color drives the inner ring. */
function indicateStyle(tag: BirthCardTag): React.CSSProperties {
  return {
    '--indicate': tag.colors[0],
    '--indicate-2': tag.colors[1] ?? tag.colors[0],
  } as React.CSSProperties;
}

/** Label text style: single color, or a gradient across all colors. */
function indicateTextStyle(tag: BirthCardTag): React.CSSProperties {
  if (tag.colors.length < 2) return { color: tag.colors[0] };
  return {
    backgroundImage: `linear-gradient(90deg, ${tag.colors.join(', ')})`,
    WebkitBackgroundClip: 'text',
    backgroundClip: 'text',
    color: 'transparent',
  };
}

export default function SpreadDisplay({ reading, onCardDoubleClick, birthLabels }: SpreadDisplayProps) {
  const { data: spread } = useQuery<Spread>({
    queryKey: ['spread', reading.spread_id],
    queryFn: () => getSpread(reading.spread_id!),
    enabled: reading.spread_id !== null && reading.spread_id !== undefined,
  });

  const cards = reading.cards_used || [];

  // If we have a spread with parsed positions, use positioned layout
  const positions: SpreadPosition[] =
    spread?.positions && Array.isArray(spread.positions) ? spread.positions : [];

  if (positions.length > 0 && cards.length > 0) {
    return <PositionedLayout cards={cards} positions={positions} spreadName={reading.spread_name} onCardDoubleClick={onCardDoubleClick} birthLabels={birthLabels} />;
  }

  // Fallback: simple card row
  return <SimpleCardRow cards={cards} spreadName={reading.spread_name} deckName={reading.deck_name} onCardDoubleClick={onCardDoubleClick} birthLabels={birthLabels} />;
}

function PositionedLayout({
  cards,
  positions,
  spreadName,
  onCardDoubleClick,
  birthLabels,
}: {
  cards: EntryReadingParsed['cards_used'];
  positions: SpreadPosition[];
  spreadName: string | null;
  onCardDoubleClick?: (cardId: number) => void;
  birthLabels?: Map<string, BirthCardTag>;
}) {
  // Calculate the actual bounding box of content (trimming empty space)
  const minX = Math.min(...positions.map(p => p.x || 0));
  const minY = Math.min(...positions.map(p => p.y || 0));
  const maxX = Math.max(...positions.map(p => (p.x || 0) + (p.width || 80)));
  const maxY = Math.max(...positions.map(p => (p.y || 0) + (p.height || 120)));

  // Content dimensions after trimming empty space
  const contentWidth = maxX - minX;
  const contentHeight = maxY - minY;

  // Use CSS to scale - we'll set a max-width and let the container handle sizing
  // The aspect ratio is maintained via the height calculation
  const aspectRatio = contentHeight / contentWidth;

  return (
    <div className="spread-display spread-display--positioned">
      {spreadName && <div className="spread-display__name">{spreadName}</div>}
      <div
        className="spread-display__canvas"
        style={{
          width: '100%',
          paddingBottom: `${aspectRatio * 100}%`,
          position: 'relative',
        }}
      >
        <div className="spread-display__canvas-inner">
          {positions.map((pos, idx) => {
            const card = cards.find(c => c.position_index === idx)
              ?? (cards[idx]?.position_index == null ? cards[idx] : undefined);
            const birthTag = birthLabelFor(card, birthLabels);
            // Calculate position as percentage of content area (offset by minX/minY)
            const leftPct = ((pos.x || 0) - minX) / contentWidth * 100;
            const topPct = ((pos.y || 0) - minY) / contentHeight * 100;
            const widthPct = (pos.width || 80) / contentWidth * 100;
            const heightPct = (pos.height || 120) / contentHeight * 100;

            return (
              <div
                key={idx}
                className={`spread-display__slot ${card?.reversed ? 'spread-display__slot--reversed' : ''} ${birthTag ? `spread-display__slot--birth ${birthTag.colors.length > 1 ? 'spread-display__slot--multi' : ''}` : ''}`}
                style={{
                  ...(birthTag ? indicateStyle(birthTag) : undefined),
                  position: 'absolute',
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                  zIndex: pos.z_index ?? idx,
                }}
                title={`${pos.label || `Position ${idx + 1}`}${card ? `: ${card.current_name || card.name}${card.reversed ? ' (R)' : ''}` : ''}`}
              >
                {/* Position badge */}
                <span className="spread-display__slot-badge">{pos.key || idx + 1}</span>
                {card ? (
                  <CardSlot
                    card={card}
                    hideLabel
                    positionRotated={pos.rotated}
                    slotWidth={pos.width || 80}
                    slotHeight={pos.height || 120}
                    onDoubleClick={onCardDoubleClick}
                  />
                ) : (
                  <div className="spread-display__empty-slot">
                    <span className="spread-display__slot-label">{pos.label || idx + 1}</span>
                  </div>
                )}
                {birthTag && (
                  <div
                    className="spread-display__birth-tag spread-display__birth-tag--overlay"
                    style={{ ...indicateStyle(birthTag), ...indicateTextStyle(birthTag) }}
                  >
                    {birthTag.label}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Extra cards (clarifiers / additional pulls beyond the
          spread's positions). Identified by stored position_index —
          saved card arrays are compacted, so length alone is no guide.
          Clarifiers are grouped one row per clarified card, so a
          reading with several clarified positions stays readable;
          unattached extras keep their own row at the end. */}
      {(() => {
        const extras = cards.filter(c => (c.position_index ?? -1) >= positions.length);
        if (extras.length === 0) return null;

        const clarifiedIndexes = Array.from(new Set(
          extras
            .map(c => c.clarifies)
            .filter((n): n is number => n != null && n >= 0 && n < positions.length),
        )).sort((a, b) => a - b);
        const unattached = extras.filter(
          c => c.clarifies == null || c.clarifies < 0 || c.clarifies >= positions.length,
        );

        const renderRow = (rowCards: typeof extras) => (
          <div className="spread-display__card-row">
            {rowCards.map((card, i) => (
              <div key={i} className="spread-display__card-item">
                <CardSlot card={card} onDoubleClick={onCardDoubleClick} birthLabel={birthLabelFor(card, birthLabels)} />
              </div>
            ))}
          </div>
        );

        return (
          <div className="spread-display__extras">
            {clarifiedIndexes.map((posIdx) => {
              const pos = positions[posIdx];
              const posLabel = pos.label || pos.key || `position ${posIdx + 1}`;
              const clarified = cards.find(c => c.position_index === posIdx);
              const clarifiedName = clarified
                ? (clarified.current_name || clarified.name)
                : null;
              return (
                <div key={posIdx} className="spread-display__extras-group">
                  <div className="spread-display__extras-title">
                    ↳ Clarifying {clarifiedName ? `${clarifiedName} (${posLabel})` : posLabel}
                  </div>
                  {renderRow(extras.filter(c => c.clarifies === posIdx))}
                </div>
              );
            })}
            {unattached.length > 0 && (
              <div className="spread-display__extras-group">
                <div className="spread-display__extras-title">Extra cards</div>
                {renderRow(unattached)}
              </div>
            )}
          </div>
        );
      })()}

      {/* Legend showing position labels and card names */}
      <div className="spread-display__legend">
        {positions.map((pos, idx) => {
          const card = cards.find(c => c.position_index === idx) || cards[idx];
          const birthTag = birthLabelFor(card, birthLabels);
          return (
            <div key={idx} className="spread-display__legend-item">
              <span className="spread-display__legend-key">{pos.key || idx + 1}</span>
              <span className="spread-display__legend-label">{pos.label || `Position ${idx + 1}`}:</span>
              <span className={`spread-display__legend-card ${card?.reversed ? 'spread-display__legend-card--reversed' : ''}`}>
                {card?.current_name || card?.name || '—'}
                {card?.reversed && <span className="spread-display__reversed-badge"> R</span>}
              </span>
              {birthTag && (
                <span
                  className="spread-display__legend-birth"
                  style={indicateTextStyle(birthTag)}
                >
                  {birthTag.label}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SimpleCardRow({
  cards,
  spreadName,
  deckName,
  onCardDoubleClick,
  birthLabels,
}: {
  cards: EntryReadingParsed['cards_used'];
  spreadName: string | null;
  deckName: string | null;
  onCardDoubleClick?: (cardId: number) => void;
  birthLabels?: Map<string, BirthCardTag>;
}) {
  return (
    <div className="spread-display">
      <div className="spread-display__header-row">
        {spreadName && <span className="spread-display__name">{spreadName}</span>}
        {deckName && <span className="spread-display__deck">{deckName}</span>}
      </div>
      {cards.length > 0 ? (
        <div className="spread-display__card-row">
          {cards.map((card, idx) => (
            <div key={idx} className="spread-display__card-item">
              <CardSlot card={card} onDoubleClick={onCardDoubleClick} birthLabel={birthLabelFor(card, birthLabels)} />
            </div>
          ))}
        </div>
      ) : (
        <div className="spread-display__no-cards">No cards recorded</div>
      )}
    </div>
  );
}

function CardSlot({
  card,
  hideLabel,
  positionRotated,
  slotWidth,
  slotHeight,
  onDoubleClick,
  birthLabel,
}: {
  card: CardUsed;
  hideLabel?: boolean;
  positionRotated?: boolean;
  slotWidth?: number;
  slotHeight?: number;
  onDoubleClick?: (cardId: number) => void;
  birthLabel?: BirthCardTag;
}) {
  const handleDoubleClick = () => {
    if (card.card_id && onDoubleClick) {
      onDoubleClick(card.card_id);
    }
  };

  // Calculate image style for rotation, handling both position rotation and card reversal
  const getImageStyle = (): React.CSSProperties | undefined => {
    const rotation = (positionRotated && card.reversed) ? 270
      : positionRotated ? 90
      : card.reversed ? 180
      : 0;

    if (rotation === 0) return undefined;
    if (rotation === 180) return { transform: 'rotate(180deg)' };

    // For 90° or 270° rotation with known slot dimensions, swap dimensions for proper sizing
    if (slotWidth && slotHeight) {
      // Calculate aspect ratio for scaling - swap because we're rotating 90°
      const scaleRatio = slotWidth / slotHeight;
      return {
        transform: `rotate(${rotation}deg) scale(${scaleRatio})`,
      };
    }

    // Fallback for cards without slot dimensions (simple card row)
    return { transform: `rotate(${rotation}deg)` };
  };

  return (
    <div
      className={`spread-display__card ${card.reversed ? 'spread-display__card--reversed' : ''} ${card.card_id && onDoubleClick ? 'spread-display__card--clickable' : ''} ${birthLabel ? `spread-display__card--birth ${birthLabel.colors.length > 1 ? 'spread-display__card--multi' : ''}` : ''}`}
      style={birthLabel ? indicateStyle(birthLabel) : undefined}
      onDoubleClick={handleDoubleClick}
    >
      {card.card_id ? (
        <img
          className="spread-display__card-img"
          src={cardPreviewUrl(card.card_id)}
          alt={card.current_name || card.name}
          style={getImageStyle()}
        />
      ) : (
        <div className="spread-display__card-placeholder" />
      )}
      {!hideLabel && (
        <div className="spread-display__card-name">
          {card.current_name || card.name}
          {card.reversed && <span className="spread-display__reversed-badge"> R</span>}
        </div>
      )}
      {birthLabel && (
        <div className="spread-display__birth-tag" style={indicateTextStyle(birthLabel)}>
          {birthLabel.label}
        </div>
      )}
    </div>
  );
}
