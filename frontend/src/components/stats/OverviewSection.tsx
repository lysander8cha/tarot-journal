import type { ExtendedStats } from '../../api/stats';

interface OverviewSectionProps {
  stats: ExtendedStats | undefined;
}

export default function OverviewSection({ stats }: OverviewSectionProps) {
  if (!stats) return null;

  const metrics = [
    { label: 'Total Entries', value: stats.total_entries },
    { label: 'This Month', value: stats.entries_this_month },
    { label: 'Total Readings', value: stats.total_readings },
    { label: 'Unique Cards', value: stats.unique_cards_drawn },
    { label: 'Avg Cards/Reading', value: stats.avg_cards_per_reading },
    { label: 'Decks', value: stats.total_decks },
  ];

  return (
    <section className="stats-tab__section">
      <h3 className="stats-tab__section-title">Overview</h3>
      <div className="stats-tab__metrics">
        {metrics.map((metric) => (
          <div key={metric.label} className="stats-tab__metric">
            <span className="stats-tab__metric-value">{metric.value}</span>
            <span className="stats-tab__metric-label">{metric.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
