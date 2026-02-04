import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { UsageStats } from '../../api/stats';

interface UsageSectionProps {
  data: UsageStats;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { name: string; count: number } }>;
}) {
  if (!active || !payload || !payload.length) return null;

  const item = payload[0].payload;
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
        {item.name}
      </div>
      <div style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
        {item.count} {item.count === 1 ? 'reading' : 'readings'}
      </div>
    </div>
  );
}

function UsageChart({ data, emptyMessage }: { data: Array<{ name: string; count: number }>; emptyMessage: string }) {
  if (!data || data.length === 0) {
    return <div className="stats-tab__chart-empty">{emptyMessage}</div>;
  }

  const chartData = data.map((item) => ({
    ...item,
    displayName: item.name.length > 22 ? item.name.slice(0, 20) + '...' : item.name,
  }));

  const chartHeight = Math.max(150, data.length * 28);

  return (
    <div className="stats-tab__chart" style={{ height: chartHeight }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
        >
          <XAxis
            type="number"
            allowDecimals={false}
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
            fill="var(--accent)"
            radius={[0, 4, 4, 0]}
            maxBarSize={20}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function UsageSection({ data }: UsageSectionProps) {
  const hasDecks = data.top_decks && data.top_decks.length > 0;
  const hasSpreads = data.top_spreads && data.top_spreads.length > 0;

  if (!hasDecks && !hasSpreads) {
    return (
      <section className="stats-tab__section">
        <h3 className="stats-tab__section-title">Most Used Decks & Spreads</h3>
        <div className="stats-tab__chart-empty">
          No readings yet. Your deck and spread usage will appear here.
        </div>
      </section>
    );
  }

  return (
    <section className="stats-tab__section">
      <h3 className="stats-tab__section-title">Most Used Decks & Spreads</h3>
      <div className="stats-tab__usage-grid">
        <div className="stats-tab__usage-column">
          <h4 className="stats-tab__usage-subtitle">Decks</h4>
          <UsageChart data={data.top_decks} emptyMessage="No deck data yet." />
        </div>
        <div className="stats-tab__usage-column">
          <h4 className="stats-tab__usage-subtitle">Spreads</h4>
          <UsageChart data={data.top_spreads} emptyMessage="No spread data yet." />
        </div>
      </div>
    </section>
  );
}
