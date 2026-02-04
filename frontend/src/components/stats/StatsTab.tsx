import { useQuery } from '@tanstack/react-query';
import {
  getExtendedStats,
  getCardFrequency,
  getTimeline,
  getTagTrends,
  getUsageStats,
} from '../../api/stats';
import type {
  ExtendedStats,
  CardFrequency,
  TimelinePeriod,
  TagTrend,
  UsageStats,
} from '../../api/stats';
import OverviewSection from './OverviewSection';
import TimelineSection from './TimelineSection';
import CardFrequencySection from './CardFrequencySection';
import TagTrendsSection from './TagTrendsSection';
import UsageSection from './UsageSection';
import './StatsTab.css';

export default function StatsTab() {
  const { data: stats, isLoading: statsLoading } = useQuery<ExtendedStats>({
    queryKey: ['extended-stats'],
    queryFn: getExtendedStats,
  });

  const { data: timeline, isLoading: timelineLoading } = useQuery<TimelinePeriod[]>({
    queryKey: ['timeline'],
    queryFn: () => getTimeline(12),
  });

  const { data: cardFrequency, isLoading: freqLoading } = useQuery<CardFrequency[]>({
    queryKey: ['card-frequency'],
    queryFn: () => getCardFrequency(20),
  });

  const { data: tagTrends, isLoading: tagsLoading } = useQuery<TagTrend[]>({
    queryKey: ['tag-trends'],
    queryFn: () => getTagTrends(15),
  });

  const { data: usage, isLoading: usageLoading } = useQuery<UsageStats>({
    queryKey: ['usage-stats'],
    queryFn: () => getUsageStats(10),
  });

  const isLoading = statsLoading || timelineLoading || freqLoading || tagsLoading || usageLoading;

  return (
    <div className="stats-tab">
      <div className="stats-tab__scroll">
        <h2 className="stats-tab__title">Insights</h2>

        {isLoading ? (
          <div className="stats-tab__loading">Loading statistics...</div>
        ) : (
          <>
            <OverviewSection stats={stats} />
            <TimelineSection data={timeline || []} />
            <CardFrequencySection data={cardFrequency || []} />
            <TagTrendsSection data={tagTrends || []} />
            {usage && <UsageSection data={usage} />}
          </>
        )}
      </div>
    </div>
  );
}
