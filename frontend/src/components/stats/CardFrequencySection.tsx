import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { CardFrequency } from '../../api/stats';

interface CardFrequencySectionProps {
  data: CardFrequency[];
}

/** Custom tooltip that shows card name, deck, and counts */
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: CardFrequency }>;
}) {
  if (!active || !payload || !payload.length) return null;

  const card = payload[0].payload;
  return (
    <div
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: '4px',
        padding: '8px 12px',
        fontSize: 'var(--font-size-body)',
      }}
    >
      <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
        {card.name}
      </div>
      <div style={{ color: 'var(--text-dim)', fontSize: 'var(--font-size-small)' }}>
        {card.deck_name}
      </div>
      <div style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
        Appearances: {card.count}
        {card.reversed_count > 0 && (
          <span style={{ color: 'var(--text-dim)' }}>
            {' '}({card.reversed_count} reversed)
          </span>
        )}
      </div>
    </div>
  );
}

export default function CardFrequencySection({ data }: CardFrequencySectionProps) {
  if (!data || data.length === 0) {
    return (
      <section className="stats-tab__section">
        <h3 className="stats-tab__section-title">Most Drawn Cards</h3>
        <div className="stats-tab__chart-empty">
          No card data yet. Create some journal entries with readings to see your most drawn cards.
        </div>
      </section>
    );
  }

  // Prepare data for chart - truncate long names for Y-axis
  const chartData = data.map((card) => ({
    ...card,
    displayName: card.name.length > 20 ? card.name.slice(0, 18) + '...' : card.name,
  }));

  // Calculate dynamic height based on number of cards
  const chartHeight = Math.max(300, data.length * 28);

  return (
    <section className="stats-tab__section">
      <h3 className="stats-tab__section-title">Most Drawn Cards</h3>
      <div className="stats-tab__chart" style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <XAxis
              type="number"
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              type="category"
              dataKey="displayName"
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={false}
              width={95}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: 'var(--bg-tertiary)' }}
            />
            <Bar
              dataKey="count"
              radius={[0, 4, 4, 0]}
              maxBarSize={20}
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill="var(--accent)"
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
