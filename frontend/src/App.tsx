import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './context/ThemeContext';
import TabNav, { type TabId } from './components/layout/TabNav';
import LibraryTab from './components/library/LibraryTab';
import JournalTab from './components/journal/JournalTab';
import SpreadsTab from './components/spreads/SpreadsTab';
import ProfilesTab from './components/profiles/ProfilesTab';
import TagsTab from './components/tags/TagsTab';
import StatsTab from './components/stats/StatsTab';
import SettingsTab from './components/settings/SettingsTab';
import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('library');

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
          <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
          <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            {activeTab === 'library' && <LibraryTab />}
            {activeTab === 'journal' && <JournalTab />}
            {activeTab === 'spreads' && <SpreadsTab />}
            {activeTab === 'profiles' && <ProfilesTab />}
            {activeTab === 'tags' && <TagsTab />}
            {activeTab === 'stats' && <StatsTab />}
            {activeTab === 'settings' && <SettingsTab />}
          </div>
        </div>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
