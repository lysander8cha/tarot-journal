import './TabNav.css';

export type TabId = 'library' | 'journal' | 'spreads' | 'profiles' | 'tags' | 'stats' | 'settings';

interface TabNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'library', label: 'Library' },
  { id: 'journal', label: 'Journal' },
  { id: 'spreads', label: 'Spreads' },
  { id: 'profiles', label: 'Profiles' },
  { id: 'tags', label: 'Tags' },
  { id: 'stats', label: 'Stats' },
  { id: 'settings', label: 'Settings' },
];

export default function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav className="tab-nav">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`tab-nav__tab ${activeTab === tab.id ? 'tab-nav__tab--active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
