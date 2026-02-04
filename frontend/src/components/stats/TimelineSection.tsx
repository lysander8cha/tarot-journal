import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { TimelinePeriod } from '../../api/stats';

interface TimelineSectionProps {
  data: TimelinePeriod[];
}

/** Format "2026-01" to "Jan '26" */
function formatPeriod(period: string): string {
  const [year, month] = period.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthName = months[parseInt(month, 10) - 1] || month;
  return `${monthName} '${year.slice(2)}`;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}) {
  if (!active || !payload || !payload.length) return null;

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
      <div style={{ color: 'var(--text-primary)', fontWeight: 500, marginBottom: '4px' }}>
        {label}
      </div>
      {payload.map((item) => (
        <div key={item.dataKey} style={{ color: 'var(--text-secondary)' }}>
          {item.dataKey === 'entries' ? 'Entries' : 'Readings'}: {item.value}
        </div>
      ))}
    </div>
  );
}

export default function TimelineSection({ data }: TimelineSectionProps) {
  if (!data || data.length === 0) {
    return (
      <section className="stats-tab__section">
        <h3 className="stats-tab__section-title">Activity Over Time</h3>
        <div className="stats-tab__chart-empty">
          No entries yet. Your reading activity will appear here over time.
        </div>
      </section>
    );
  }

  // Format period labels for display
  const chartData = data.map((d) => ({
    ...d,
    label: formatPeriod(d.period),
  }));

  return (
    <section className="stats-tab__section">
      <h3 className="stats-tab__section-title">Activity Over Time</h3>
      <div className="stats-tab__chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <XAxis
              dataKey="label"
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={{ stroke: 'var(--border)' }}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--bg-tertiary)' }} />
            <Legend
              wrapperStyle={{ fontSize: 'var(--font-size-small)', color: 'var(--text-secondary)' }}
            />
            <Bar
              dataKey="entries"
              name="Entries"
              fill="var(--accent)"
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
            />
            <Bar
              dataKey="readings"
              name="Readings"
              fill="var(--accent-dim)"
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
