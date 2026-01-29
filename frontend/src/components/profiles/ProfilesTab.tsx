import { useState, useEffect } from 'react';
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

  // Form state
  const [name, setName] = useState('');
  const [gender, setGender] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [birthTime, setBirthTime] = useState('');
  const [birthPlaceName, setBirthPlaceName] = useState('');
  const [querentOnly, setQuerentOnly] = useState(false);

  const { data: profiles = [], isLoading } = useQuery<Profile[]>({
    queryKey: ['profiles'],
    queryFn: getProfiles,
  });

  const selectedProfile = profiles.find((p) => p.id === selectedId) ?? null;

  // Populate form when selection changes
  useEffect(() => {
    if (selectedProfile && !isNew) {
      setName(selectedProfile.name);
      setGender(selectedProfile.gender || '');
      setBirthDate(selectedProfile.birth_date || '');
      setBirthTime(selectedProfile.birth_time || '');
      setBirthPlaceName(selectedProfile.birth_place_name || '');
      setQuerentOnly(selectedProfile.querent_only || false);
    }
  }, [selectedProfile, isNew]);

  const handleSelect = (profile: Profile) => {
    setSelectedId(profile.id);
    setIsNew(false);
  };

  const handleNew = () => {
    setSelectedId(null);
    setIsNew(true);
    setName('');
    setGender('');
    setBirthDate('');
    setBirthTime('');
    setBirthPlaceName('');
    setQuerentOnly(false);
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const data = {
        name: name.trim(),
        gender: gender.trim() || null,
        birth_date: birthDate || null,
        birth_time: birthTime || null,
        birth_place_name: birthPlaceName.trim() || null,
        querent_only: querentOnly,
      };

      if (isNew) {
        const result = await createProfile(data);
        setSelectedId(result.id);
        setIsNew(false);
      } else if (selectedId) {
        await updateProfile(selectedId, data);
      }

      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    } catch (err) {
      console.error('Failed to save profile:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    if (!window.confirm(`Delete "${selectedProfile?.name}"? Journal entries referencing this profile will have their querent/reader cleared.`)) return;
    try {
      await deleteProfile(selectedId);
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setSelectedId(null);
      setIsNew(false);
    } catch (err) {
      console.error('Failed to delete profile:', err);
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
              </div>

              <div className="profiles-tab__footer">
                {!isNew && (
                  <button className="profiles-tab__delete-btn" onClick={handleDelete}>
                    Delete
                  </button>
                )}
                <button
                  className="profiles-tab__save-btn"
                  onClick={handleSave}
                  disabled={saving || !name.trim()}
                >
                  {saving ? 'Saving...' : isNew ? 'Create' : 'Save'}
                </button>
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
