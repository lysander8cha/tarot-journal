import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { TagTrend } from '../../api/stats';

interface TagTrendsSectionProps {
  data: TagTrend[];
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: TagTrend }>;
}) {
  if (!active || !payload || !payload.length) return null;

  const tag = payload[0].payload;
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
      <div style={{ color: tag.color, fontWeight: 500 }}>
        {tag.name}
      </div>
      <div style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
        {tag.count} {tag.count === 1 ? 'entry' : 'entries'}
      </div>
    </div>
  );
}

export default function TagTrendsSection({ data }: TagTrendsSectionProps) {
  if (!data || data.length === 0) {
    return (
      <section className="stats-tab__section">
        <h3 className="stats-tab__section-title">Tag Trends</h3>
        <div className="stats-tab__chart-empty">
          No tagged entries yet. Tag your journal entries to see trends here.
        </div>
      </section>
    );
  }

  const chartData = data.map((tag) => ({
    ...tag,
    displayName: tag.name.length > 20 ? tag.name.slice(0, 18) + '...' : tag.name,
  }));

  const chartHeight = Math.max(200, data.length * 28);

  return (
    <section className="stats-tab__section">
      <h3 className="stats-tab__section-title">Tag Trends</h3>
      <div className="stats-tab__chart" style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
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
              width={75}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: 'var(--bg-tertiary)' }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={20}>
              {chartData.map((tag, index) => (
                <Cell key={`cell-${index}`} fill={tag.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
