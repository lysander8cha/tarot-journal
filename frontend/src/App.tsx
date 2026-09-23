import { useState, useCallback, useEffect, useRef } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmDialogHost } from './components/common/ConfirmDialog';
import { installQuitGuard, hasDirtyEditors } from './utils/dirtyGuard';
import { confirmDialog } from './components/common/ConfirmDialog';
import TabNav, { type TabId } from './components/layout/TabNav';
import CommandPalette, { type PaletteAction } from './components/common/CommandPalette';
import ScribeLauncher from './components/scribe/ScribeLauncher';
import WelcomeModal from './components/onboarding/WelcomeModal';
import GettingStartedPanel from './components/onboarding/GettingStartedPanel';
import GuideOverlay from './components/onboarding/GuideOverlay';
import { TOURS, type Tour } from './components/onboarding/tours';
import { getOnboardingFlags } from './api/onboarding';
import { getPushActivity } from './api/sync';
import { getProfiles } from './api/profiles';
import { getDecks } from './api/decks';
import ShortcutsOverlay from './components/common/ShortcutsOverlay';
import LibraryTab from './components/library/LibraryTab';
import JournalTab from './components/journal/JournalTab';
import SpreadsTab from './components/spreads/SpreadsTab';
import ReferenceTab, { type ReferenceSectionId } from './components/reference/ReferenceTab';
import ProfilesTab from './components/profiles/ProfilesTab';
import StatsTab from './components/stats/StatsTab';
import SettingsTab from './components/settings/SettingsTab';
/* Style stack, in load order: Nocturne ramps → tj application tokens →
   bundled fonts → base styles (compat layer + primitives). */
import './styles/nocturne.css';
import './styles/tokens.css';
import './styles/accent-steel.css';
import './styles/fonts.css';
import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

interface SettingsDeepLinkPayload {
  combination?: {
    cartomancy_type: string;
    archetype_1_id: number;
    archetype_2_id: number;
    archetype_1_reversed?: boolean;
    archetype_2_reversed?: boolean;
  };
  archetypeId?: number;
}

/** One place the user has been: a tab plus whatever deep-link narrows
 *  it (a deck, an entry, an archetype, a reference or settings
 *  section, a journal card filter). The back/forward history is a
 *  stack of these. */
interface AppLocation {
  tab: TabId;
  deckId?: number;
  spreadId?: number;
  entryId?: number;
  archetype?: { id: number; cartomancyType: string };
  referenceSection?: ReferenceSectionId;
  settingsSection?: string;
  /** Carried for replay but not part of location identity. */
  settingsPayload?: SettingsDeepLinkPayload;
  journalCardFilter?: string;
}

function locationKey(loc: AppLocation): string {
  return JSON.stringify([
    loc.tab, loc.deckId ?? null, loc.spreadId ?? null, loc.entryId ?? null,
    loc.archetype?.id ?? null, loc.referenceSection ?? null,
    loc.settingsSection ?? null, loc.journalCardFilter ?? null,
  ]);
}

const HISTORY_LIMIT = 100;

/** A deep-link that can also express "nothing selected": the token
 *  makes every application distinct, so re-applying the same id (or
 *  clearing) after the user wandered off still takes effect. */
export interface SelectionLink {
  id: number | null;
  token: number;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('library');
  const [settingsSection, setSettingsSection] = useState<string | undefined>();
  const [settingsPayload, setSettingsPayload] = useState<SettingsDeepLinkPayload | undefined>();
  const [pendingNewEntry, setPendingNewEntry] = useState(false);
  // "Find in Journal" from the card viewer: jump to the Journal tab
  // filtered to entries containing a card. Lives here because it's
  // set from the Library tab and consumed by the Journal tab.
  const [journalCardFilter, setJournalCardFilter] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [scribeOpen, setScribeOpen] = useState(false);
  // Deep-links into tabs. Library and Journal use token-bearing
  // SelectionLinks (history can restore or clear a selection); the
  // others keep the consume-and-clear pending pattern.
  const [deckLink, setDeckLink] = useState<SelectionLink | null>(null);
  const [entryLink, setEntryLink] = useState<SelectionLink | null>(null);
  const [pendingSpreadId, setPendingSpreadId] = useState<number | null>(null);
  const [pendingArchetype, setPendingArchetype] =
    useState<{ id: number; cartomancyType: string } | null>(null);
  const [referenceSection, setReferenceSection] =
    useState<ReferenceSectionId | undefined>();
  const linkToken = useRef(0);

  // === Browser-style history ===
  const [history, setHistory] = useState<{ stack: AppLocation[]; cursor: number }>({
    stack: [{ tab: 'library' }],
    cursor: 0,
  });

  /** Append a location (drops any forward branch). No-op when it
   *  matches where we already are — selections applied FROM history
   *  report back through the same paths and must not re-push. */
  const record = useCallback((loc: AppLocation) => {
    setHistory(h => {
      if (locationKey(h.stack[h.cursor]) === locationKey(loc)) return h;
      const stack = [...h.stack.slice(0, h.cursor + 1), loc].slice(-HISTORY_LIMIT);
      return { stack, cursor: stack.length - 1 };
    });
  }, []);

  /** Make the app show a location: switch tab and re-fire its deep
   *  link through the normal pending/link plumbing. */
  const applyLocation = useCallback((loc: AppLocation) => {
    setActiveTab(loc.tab);
    switch (loc.tab) {
      case 'library':
        setDeckLink({ id: loc.deckId ?? null, token: ++linkToken.current });
        break;
      case 'journal':
        setJournalCardFilter(loc.journalCardFilter ?? null);
        setEntryLink({ id: loc.entryId ?? null, token: ++linkToken.current });
        break;
      case 'spreads':
        if (loc.spreadId != null) setPendingSpreadId(loc.spreadId);
        break;
      case 'reference':
        if (loc.archetype) setPendingArchetype(loc.archetype);
        else if (loc.referenceSection) setReferenceSection(loc.referenceSection);
        break;
      case 'settings':
        if (loc.settingsSection) {
          setSettingsSection(loc.settingsSection);
          setSettingsPayload(loc.settingsPayload);
        }
        break;
      default:
        break;
    }
  }, []);

  // Switching top-level tabs unmounts the current tab's editors, so a
  // dirty non-modal editor (e.g. a half-designed spread) would lose
  // its work silently. Every navigation path goes through this guard.
  const confirmLeave = useCallback(async (tab: TabId): Promise<boolean> => {
    if (tab !== activeTab && hasDirtyEditors()) {
      return confirmDialog({
        title: 'Unsaved Changes',
        message: 'You have unsaved changes. Switch tabs and discard them?',
        confirmLabel: 'Discard & Switch',
      });
    }
    return true;
  }, [activeTab]);

  /** Guarded navigation: record + apply. */
  const navigate = useCallback(async (loc: AppLocation): Promise<boolean> => {
    if (!(await confirmLeave(loc.tab))) return false;
    record(loc);
    applyLocation(loc);
    return true;
  }, [confirmLeave, record, applyLocation]);

  const canGoBack = history.cursor > 0;
  const canGoForward = history.cursor < history.stack.length - 1;

  const goBack = useCallback(async () => {
    if (history.cursor <= 0) return;
    const target = history.stack[history.cursor - 1];
    if (!(await confirmLeave(target.tab))) return;
    setHistory(h => ({ ...h, cursor: Math.max(0, h.cursor - 1) }));
    applyLocation(target);
  }, [history, confirmLeave, applyLocation]);

  const goForward = useCallback(async () => {
    if (history.cursor >= history.stack.length - 1) return;
    const target = history.stack[history.cursor + 1];
    if (!(await confirmLeave(target.tab))) return;
    setHistory(h => ({ ...h, cursor: Math.min(h.stack.length - 1, h.cursor + 1) }));
    applyLocation(target);
  }, [history, confirmLeave, applyLocation]);

  const handleFindCardInJournal = useCallback(async (cardName: string) => {
    await navigate({ tab: 'journal', journalCardFilter: cardName });
  }, [navigate]);

  const handleClearCardFilter = useCallback(() => {
    setJournalCardFilter(null);
    record({ tab: 'journal' });
  }, [record]);

  // Block app quit / reload while any editor has unsaved changes.
  useEffect(() => {
    installQuitGuard();
  }, []);

  // Cmd+N (Ctrl+N elsewhere) starts a new journal entry from any tab —
  // the app's single most common action. Cmd+K opens the command
  // palette. Cmd+[ / Cmd+] walk the navigation history. All are
  // ignored while a dialog is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // "?" (no modifiers beyond Shift) shows the shortcuts cheat
      // sheet — unless focus is in a text field, where ? is just typing.
      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = e.target as HTMLElement | null;
        if (target && (
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable
        )) return;
        e.preventDefault();
        setShortcutsOpen(open => {
          if (open) return false;
          return !document.querySelector('.modal-overlay, .confirm-dialog__overlay');
        });
        return;
      }
      if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === 'k') {
        e.preventDefault();
        setPaletteOpen(open => {
          if (open) return false;
          // Don't open over another dialog.
          return !document.querySelector('.modal-overlay, .confirm-dialog__overlay');
        });
      } else if (key === 'n') {
        if (document.querySelector('.modal-overlay, .confirm-dialog__overlay')) return;
        e.preventDefault();
        (async () => {
          if (activeTab !== 'journal' && !(await navigate({ tab: 'journal' }))) return;
          setPendingNewEntry(true);
        })();
      } else if (key === '[' || key === ']') {
        if (document.querySelector('.modal-overlay, .confirm-dialog__overlay')) return;
        e.preventDefault();
        if (key === '[') goBack(); else goForward();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeTab, navigate, goBack, goForward]);

  // Command palette selections land here.
  const handlePaletteAction = useCallback(async (action: PaletteAction) => {
    switch (action.type) {
      case 'tab':
        if (action.tab !== activeTab) await navigate({ tab: action.tab });
        break;
      case 'settings':
        await navigate({ tab: 'settings', settingsSection: action.section });
        break;
      case 'new-entry':
        if (activeTab !== 'journal' && !(await navigate({ tab: 'journal' }))) break;
        setPendingNewEntry(true);
        break;
      case 'shortcuts':
        setShortcutsOpen(true);
        break;
      case 'scribe':
        setScribeOpen(true);
        break;
      case 'deck':
        await navigate({ tab: 'library', deckId: action.id });
        break;
      case 'spread':
        await navigate({ tab: 'spreads', spreadId: action.id });
        break;
      case 'entry':
        await navigate({ tab: 'journal', entryId: action.id });
        break;
      case 'archetype':
        await navigate({
          tab: 'reference',
          archetype: { id: action.id, cartomancyType: action.cartomancyType },
        });
        break;
      case 'reference':
        await navigate({
          tab: 'reference',
          referenceSection: action.section as ReferenceSectionId,
        });
        break;
    }
  }, [activeTab, navigate]);

  const handleNewEntryHandled = useCallback(() => setPendingNewEntry(false), []);

  const handleTabChange = useCallback(async (tab: TabId, section?: string) => {
    // Clicking the tab you're on is a no-op (re-applying would clear
    // the tab's current selection).
    if (tab === activeTab && !section) return;
    await navigate({ tab, settingsSection: section });
  }, [activeTab, navigate]);

  const handleSettingsSectionViewed = useCallback(() => {
    setSettingsSection(undefined);
    setSettingsPayload(undefined);
  }, []);

  const handleNavigateToSettings = useCallback(
    (section: string, payload?: SettingsDeepLinkPayload) => {
      navigate({ tab: 'settings', settingsSection: section, settingsPayload: payload });
    },
    [navigate],
  );

  const handleOpenArchetype = useCallback((id: number, cartomancyType: string) => {
    navigate({ tab: 'reference', archetype: { id, cartomancyType } });
  }, [navigate]);

  // Selections reported by the tabs so history can restore them.
  const handleDeckSelected = useCallback((id: number | null) => {
    record({ tab: 'library', deckId: id ?? undefined });
  }, [record]);

  const handleEntrySelected = useCallback((id: number | null) => {
    record({
      tab: 'journal',
      entryId: id ?? undefined,
      journalCardFilter: journalCardFilter ?? undefined,
    });
  }, [record, journalCardFilter]);

  const handleReferenceSectionChange = useCallback((section: ReferenceSectionId) => {
    record({ tab: 'reference', referenceSection: section });
  }, [record]);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            <TabNav
              activeTab={activeTab}
              onTabChange={handleTabChange}
              canGoBack={canGoBack}
              canGoForward={canGoForward}
              onBack={goBack}
              onForward={goForward}
            />
            <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
              {activeTab === 'library' && (
                <LibraryTab
                  onFindCardInJournal={handleFindCardInJournal}
                  deckLink={deckLink}
                  onDeckSelected={handleDeckSelected}
                />
              )}
              {activeTab === 'spreads' && (
                <SpreadsTab
                  pendingSpreadId={pendingSpreadId}
                  onPendingSpreadHandled={() => setPendingSpreadId(null)}
                />
              )}
              {activeTab === 'journal' && (
                <JournalTab
                  pendingNewEntry={pendingNewEntry}
                  onNewEntryHandled={handleNewEntryHandled}
                  cardFilter={journalCardFilter}
                  onClearCardFilter={handleClearCardFilter}
                  onFindCardInJournal={handleFindCardInJournal}
                  entryLink={entryLink}
                  onEntrySelected={handleEntrySelected}
                />
              )}
              {activeTab === 'profiles' && <ProfilesTab />}
              {activeTab === 'reference' && (
                <ReferenceTab
                  onNavigateToSettings={handleNavigateToSettings}
                  pendingArchetype={pendingArchetype}
                  onPendingArchetypeHandled={() => setPendingArchetype(null)}
                  initialSection={referenceSection}
                  onSectionViewed={() => setReferenceSection(undefined)}
                  onSectionChange={handleReferenceSectionChange}
                  onOpenArchetype={handleOpenArchetype}
                />
              )}
              {activeTab === 'insights' && <StatsTab />}
              {activeTab === 'settings' && (
                <SettingsTab
                  initialSection={settingsSection}
                  initialCombination={settingsPayload?.combination}
                  initialArchetypeId={settingsPayload?.archetypeId}
                  onSectionViewed={handleSettingsSectionViewed}
                />
              )}
            </div>
          </div>
          <CommandPalette
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            onAction={handlePaletteAction}
          />
          <ShortcutsOverlay
            open={shortcutsOpen}
            onClose={() => setShortcutsOpen(false)}
          />
          {scribeOpen && (
            <ScribeLauncher open onClose={() => setScribeOpen(false)} />
          )}
          <OnboardingHost onGoTo={(tab) => { void navigate({ tab }); }} />
          <PhonePushWatcher />
          <ConfirmDialogHost />
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/** Mounts first-run onboarding: the welcome modal (empty database,
 *  never seen before) and the Getting Started checklist (until its
 *  items are done or it's dismissed). Established databases satisfy
 *  every item, so existing users never see either. */
function OnboardingHost({ onGoTo }: { onGoTo: (tab: TabId) => void }) {
  const { data: flags } = useQuery({
    queryKey: ['onboarding-flags'],
    queryFn: getOnboardingFlags,
  });
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: getProfiles });
  const { data: decks } = useQuery({ queryKey: ['decks'], queryFn: () => getDecks() });
  const [welcomeClosed, setWelcomeClosed] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [tour, setTour] = useState<Tour | null>(null);

  if (!flags || !profiles || !decks) return null;

  const welcomeOpen =
    !flags.welcome_done && !welcomeClosed
    && profiles.length === 0 && decks.length === 0;
  const showChecklist = !flags.checklist_dismissed && !dismissed && !welcomeOpen;

  return (
    <>
      <WelcomeModal
        open={welcomeOpen}
        onClose={() => setWelcomeClosed(true)}
        onGoTo={(tab) => {
          onGoTo(tab);
          if (tab === 'library') setTour(TOURS.deck);
        }}
      />
      {showChecklist && (
        <GettingStartedPanel
          onGoTo={onGoTo}
          onDismissed={() => setDismissed(true)}
          onStartTour={(id) => setTour(TOURS[id])}
        />
      )}
      {tour && <GuideOverlay key={tour.id} tour={tour} onDone={() => setTour(null)} />}
    </>
  );
}

/** Polls the backend's last-phone-push stamp (a few bytes every 15s)
 *  and refreshes the journal caches when it changes — so an entry
 *  logged on the phone appears in the open desktop app within
 *  seconds instead of after a restart. */
function PhonePushWatcher() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ['phone-push-activity'],
    queryFn: getPushActivity,
    refetchInterval: 15_000,
  });
  const prev = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (data === undefined) return;
    const stamp = data.last_push_at ?? null;
    if (prev.current !== undefined && stamp !== prev.current) {
      queryClient.invalidateQueries({ queryKey: ['entries'] });
      queryClient.invalidateQueries({ queryKey: ['entry-search'] });
      queryClient.invalidateQueries({ queryKey: ['entry-tags'] });
    }
    prev.current = stamp;
  }, [data, queryClient]);
  return null;
}
