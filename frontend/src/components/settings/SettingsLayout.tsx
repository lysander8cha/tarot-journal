import { useState, useEffect } from 'react';
import GeneralSection from './sections/GeneralSection';
import TagsTab from '../tags/TagsTab';
import ImportPresetsSection from './sections/ImportPresetsSection';
import BackupSection from './sections/BackupSection';
import CacheSection from './sections/CacheSection';
import CorrespondencesSection from './sections/CorrespondencesSection';
import DeckTypesSection from './sections/DeckTypesSection';
import CombinationsSection from './sections/CombinationsSection';
import ArchetypeNotesSection from './sections/ArchetypeNotesSection';
import ArchetypeLanguagesSection from './sections/ArchetypeLanguagesSection';
import ReferenceSourcesSection from './sections/ReferenceSourcesSection';
import AiSection from './sections/AiSection';
import AiPromptsSection from './sections/AiPromptsSection';
import './SettingsLayout.css';

export type SettingsSectionId =
  | 'general'
  | 'deck-types'
  | 'tags'
  | 'correspondences'
  | 'archetype-notes'
  | 'archetype-languages'
  | 'combinations'
  | 'reference-sources'
  | 'import-presets'
  | 'backup'
  | 'cache'
  | 'ai'
  | 'ai-prompts';

// Grouped so the sidebar reads as three ideas instead of a flat
// 11-item list: app-level settings, the user's people/tags, and the
// editors for reference content that's *viewed* in the Reference tab.
const SECTION_GROUPS: {
  heading: string | null;
  sections: { id: SettingsSectionId; label: string }[];
}[] = [
  {
    heading: null,
    sections: [
      { id: 'general', label: 'General' },
      { id: 'ai', label: 'AI Assistant' },
      { id: 'ai-prompts', label: 'AI Prompts' },
      { id: 'backup', label: 'Backup & Restore' },
      { id: 'cache', label: 'Thumbnail Cache' },
    ],
  },
  {
    heading: 'Tags',
    sections: [
      { id: 'tags', label: 'Tags' },
    ],
  },
  {
    heading: 'Reference Data',
    sections: [
      { id: 'deck-types', label: 'Deck Types' },
      { id: 'correspondences', label: 'Correspondences' },
      { id: 'archetype-notes', label: 'Archetype Notes' },
      { id: 'archetype-languages', label: 'Archetype Languages' },
      { id: 'combinations', label: 'Combinations' },
      { id: 'reference-sources', label: 'Reference Sources' },
      { id: 'import-presets', label: 'Import Presets' },
    ],
  },
];

const SECTIONS = SECTION_GROUPS.flatMap(g => g.sections);

interface SettingsLayoutProps {
  initialSection?: string;
  /** Optional pre-selected combination for the Combinations editor. */
  initialCombination?: {
    cartomancy_type: string;
    archetype_1_id: number;
    archetype_2_id: number;
    archetype_1_reversed?: boolean;
    archetype_2_reversed?: boolean;
  };
  /** Optional pre-selected archetype id for Archetype Notes / Languages editors. */
  initialArchetypeId?: number;
  onSectionViewed?: () => void;
}

export default function SettingsLayout({
  initialSection,
  initialCombination,
  initialArchetypeId,
  onSectionViewed,
}: SettingsLayoutProps) {
  const [activeSection, setActiveSection] = useState<SettingsSectionId>('general');

  useEffect(() => {
    if (initialSection && SECTIONS.some(s => s.id === initialSection)) {
      setActiveSection(initialSection as SettingsSectionId);
      onSectionViewed?.();
    }
  }, [initialSection, onSectionViewed]);

  return (
    <div className="settings-layout">
      <nav className="settings-layout__sidebar">
        {SECTION_GROUPS.map((group, gi) => (
          <div key={group.heading ?? `group-${gi}`} className="settings-layout__nav-group">
            {group.heading && (
              <div className="settings-layout__nav-heading">{group.heading}</div>
            )}
            {group.sections.map((section) => (
              <button
                key={section.id}
                className={`settings-layout__nav-item ${activeSection === section.id ? 'settings-layout__nav-item--active' : ''}`}
                onClick={() => setActiveSection(section.id)}
              >
                {section.label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="settings-layout__content">
        {activeSection === 'general' && <GeneralSection />}
        {activeSection === 'tags' && <TagsTab />}
        {activeSection === 'deck-types' && <DeckTypesSection />}
        {activeSection === 'correspondences' && <CorrespondencesSection />}
        {activeSection === 'archetype-notes' && (
          <ArchetypeNotesSection initialArchetypeId={initialArchetypeId} />
        )}
        {activeSection === 'archetype-languages' && (
          <ArchetypeLanguagesSection initialArchetypeId={initialArchetypeId} />
        )}
        {activeSection === 'combinations' && (
          <CombinationsSection
            initialCombination={initialCombination}
          />
        )}
        {activeSection === 'reference-sources' && <ReferenceSourcesSection />}
        {activeSection === 'import-presets' && <ImportPresetsSection />}
        {activeSection === 'backup' && <BackupSection />}
        {activeSection === 'cache' && <CacheSection />}
        {activeSection === 'ai' && <AiSection />}
        {activeSection === 'ai-prompts' && <AiPromptsSection />}
      </div>
    </div>
  );
}
