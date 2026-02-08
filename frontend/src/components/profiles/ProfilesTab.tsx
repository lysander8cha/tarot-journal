import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Panel, Group, Separator } from 'react-resizable-panels';
import {
  getProfiles,
  createProfile,
  updateProfile,
  deleteProfile,
} from '../../api/profiles';
import type { Profile } from '../../types';
import './ProfilesTab.css';

export default function ProfilesTab() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [error, setError] = useState('');

  // Form state
  const [name, setName] = useState('');
  const [gender, setGender] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [birthTime, setBirthTime] = useState('');
  const [birthPlaceName, setBirthPlaceName] = useState('');
  const [querentOnly, setQuerentOnly] = useState(false);
  const [hidden, setHidden] = useState(false);

  // Track whether form was just populated (to skip auto-save on initial load)
  const populatingRef = useRef(false);
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: profiles = [], isLoading } = useQuery<Profile[]>({
    queryKey: ['profiles'],
    queryFn: getProfiles,
  });

  const selectedProfile = profiles.find((p) => p.id === selectedId) ?? null;

  // Populate form when selection changes
  useEffect(() => {
    if (selectedProfile && !isNew) {
      populatingRef.current = true;
      setName(selectedProfile.name);
      setGender(selectedProfile.gender || '');
      setBirthDate(selectedProfile.birth_date || '');
      setBirthTime(selectedProfile.birth_time || '');
      setBirthPlaceName(selectedProfile.birth_place_name || '');
      setQuerentOnly(selectedProfile.querent_only || false);
      setHidden(selectedProfile.hidden || false);
      setSaveStatus('idle');
      setError('');
      // Allow the state updates to flush before re-enabling auto-save
      requestAnimationFrame(() => { populatingRef.current = false; });
    }
  }, [selectedProfile, isNew]);

  // Auto-save for existing profiles
  const doAutoSave = useCallback(async () => {
    if (!selectedId || isNew || !name.trim()) return;
    setSaveStatus('saving');
    setError('');
    try {
      await updateProfile(selectedId, {
        name: name.trim(),
        gender: gender.trim() || null,
        birth_date: birthDate || null,
        birth_time: birthTime || null,
        birth_place_name: birthPlaceName.trim() || null,
        querent_only: querentOnly,
        hidden: hidden,
      });
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setSaveStatus('saved');
    } catch (err) {
      console.error('Failed to save profile:', err);
      setError('Failed to save profile.');
      setSaveStatus('idle');
    }
  }, [selectedId, isNew, name, gender, birthDate, birthTime, birthPlaceName, querentOnly, hidden, queryClient]);

  // Debounced auto-save effect
  useEffect(() => {
    if (populatingRef.current || isNew || !selectedId) return;
    if (!name.trim()) return;

    setSaveStatus('idle');
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      doAutoSave();
    }, 600);

    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [name, gender, birthDate, birthTime, birthPlaceName, querentOnly, hidden, selectedId, isNew, doAutoSave]);

  const handleSelect = (profile: Profile) => {
    // Flush any pending auto-save immediately
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    setSelectedId(profile.id);
    setIsNew(false);
  };

  const handleNew = () => {
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    setSelectedId(null);
    setIsNew(true);
    setName('');
    setGender('');
    setBirthDate('');
    setBirthTime('');
    setBirthPlaceName('');
    setQuerentOnly(false);
    setHidden(false);
    setSaveStatus('idle');
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const data = {
        name: name.trim(),
        gender: gender.trim() || null,
        birth_date: birthDate || null,
        birth_time: birthTime || null,
        birth_place_name: birthPlaceName.trim() || null,
        querent_only: querentOnly,
        hidden: hidden,
      };
      const result = await createProfile(data);
      setSelectedId(result.id);
      setIsNew(false);
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    } catch (err) {
      console.error('Failed to create profile:', err);
      setError('Failed to create profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    if (!window.confirm(`Delete "${selectedProfile?.name}"? Journal entries referencing this profile will have their querent/reader cleared.`)) return;
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    setError('');
    try {
      await deleteProfile(selectedId);
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setSelectedId(null);
      setIsNew(false);
    } catch (err) {
      console.error('Failed to delete profile:', err);
      setError('Failed to delete profile. Please try again.');
    }
  };

  const hasSelection = selectedId !== null || isNew;

  return (
    <div className="profiles-tab">
      <Group orientation="horizontal" style={{ width: '100%', height: '100%' }}>
        <Panel defaultSize="30%" minSize="20%">
          <div className="profiles-tab__list">
            <div className="profiles-tab__list-header">
              <h2 className="profiles-tab__list-title">Profiles</h2>
              <button onClick={handleNew}>+ New</button>
            </div>
            <div className="profiles-tab__rows">
              {isLoading && <div className="profiles-tab__empty">Loading...</div>}
              {profiles.map((profile) => (
                <div
                  key={profile.id}
                  className={`profiles-tab__row ${profile.id === selectedId ? 'profiles-tab__row--selected' : ''}`}
                  onClick={() => handleSelect(profile)}
                >
                  <span className="profiles-tab__row-name">{profile.name}</span>
                  {profile.gender && (
                    <span className="profiles-tab__row-gender">{profile.gender}</span>
                  )}
                </div>
              ))}
              {!isLoading && profiles.length === 0 && (
                <div className="profiles-tab__empty">No profiles yet</div>
              )}
            </div>
          </div>
        </Panel>
        <Separator className="resize-handle" />
        <Panel minSize="30%">
          {hasSelection ? (
            <div className="profiles-tab__form-panel">
              <div className="profiles-tab__form-scroll">
                <h3 className="profiles-tab__form-title">
                  {isNew ? 'New Profile' : 'Edit Profile'}
                </h3>

                {error && <div className="profiles-tab__error">{error}</div>}

                <div className="profiles-tab__field">
                  <label className="profiles-tab__label">Name *</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Profile name"
                  />
                </div>

                <div className="profiles-tab__field">
                  <label className="profiles-tab__label">Gender</label>
                  <input
                    type="text"
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    placeholder="e.g. Female, Male, Non-binary"
                  />
                </div>

                <div className="profiles-tab__row-fields">
                  <div className="profiles-tab__field">
                    <label className="profiles-tab__label">Birth Date</label>
                    <input
                      type="date"
                      value={birthDate}
                      onChange={(e) => setBirthDate(e.target.value)}
                    />
                  </div>
                  <div className="profiles-tab__field">
                    <label className="profiles-tab__label">Birth Time</label>
                    <input
                      type="time"
                      value={birthTime}
                      onChange={(e) => setBirthTime(e.target.value)}
                    />
                  </div>
                </div>

                <div className="profiles-tab__field">
                  <label className="profiles-tab__label">Birth Place</label>
                  <input
                    type="text"
                    value={birthPlaceName}
                    onChange={(e) => setBirthPlaceName(e.target.value)}
                    placeholder="City, Country"
                  />
                </div>

                <div className="profiles-tab__field profiles-tab__checkbox-field">
                  <label className="profiles-tab__checkbox-label">
                    <input
                      type="checkbox"
                      checked={querentOnly}
                      onChange={(e) => setQuerentOnly(e.target.checked)}
                    />
                    <span>Querent Only</span>
                  </label>
                </div>

                <div className="profiles-tab__field profiles-tab__checkbox-field">
                  <label className="profiles-tab__checkbox-label">
                    <input
                      type="checkbox"
                      checked={hidden}
                      onChange={(e) => setHidden(e.target.checked)}
                    />
                    <span>Hide from dropdowns</span>
                  </label>
                </div>
              </div>

              <div className="profiles-tab__footer">
                {!isNew && (
                  <button className="profiles-tab__delete-btn" onClick={handleDelete}>
                    Delete
                  </button>
                )}
                {isNew ? (
                  <button
                    className="profiles-tab__save-btn"
                    onClick={handleCreate}
                    disabled={saving || !name.trim()}
                  >
                    {saving ? 'Creating...' : 'Create'}
                  </button>
                ) : (
                  <span className={`profiles-tab__status ${saveStatus !== 'idle' ? 'profiles-tab__status--visible' : ''}`}>
                    {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : ''}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="profiles-tab__empty-panel">
              Select a profile or click "New" to create one.
            </div>
          )}
        </Panel>
      </Group>
    </div>
  );
}
