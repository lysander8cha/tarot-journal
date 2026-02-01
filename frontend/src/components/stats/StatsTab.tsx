import { useQuery } from '@tanstack/react-query';
import { getExtendedStats, getCardFrequency } from '../../api/stats';
import type { ExtendedStats, CardFrequency } from '../../api/stats';
import OverviewSection from './OverviewSection';
import CardFrequencySection from './CardFrequencySection';
import './StatsTab.css';

export default function StatsTab() {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery<ExtendedStats>({
    queryKey: ['extended-stats'],
    queryFn: getExtendedStats,
  });

  const {
    data: cardFrequency,
    isLoading: freqLoading,
    error: freqError,
  } = useQuery<CardFrequency[]>({
    queryKey: ['card-frequency'],
    queryFn: () => getCardFrequency(20),
  });

  const isLoading = statsLoading || freqLoading;
  const hasError = statsError || freqError;

  return (
    <div className="stats-tab">
      <div className="stats-tab__scroll">
        <h2 className="stats-tab__title">Insights</h2>

        {hasError && (
          <div className="stats-tab__error">
            Failed to load statistics. Please try again.
          </div>
        )}

        {isLoading ? (
          <div className="stats-tab__loading">Loading statistics...</div>
        ) : (
          <>
            {/* Overview metrics */}
            <OverviewSection stats={stats} />

            {/* Card frequency chart */}
            <CardFrequencySection data={cardFrequency || []} />

            {/* Placeholder for future sections */}
            {/* <TimelineSection data={timeline} /> */}
            {/* <TagUsageSection data={tagUsage} /> */}
          </>
        )}
      </div>
    </div>
  );
}
