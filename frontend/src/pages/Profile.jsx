import { useState, useEffect } from 'react';
import ProfileView from '../components/profile/ProfileView';
import ProfileEditForm from '../components/profile/ProfileEditForm';
import { getMyProfile, updateMyProfile, addPastRole, removePastRole } from '../api/profile';

const Profile = () => {
  const [profile, setProfile] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    getMyProfile({ signal: controller.signal })
      .then(setProfile)
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message || 'Could not load your profile.');
      });
    return () => controller.abort();
  }, []);

  const handleSave = async (updatedProfile) => {
    try {
      const saved = await updateMyProfile(updatedProfile);
      setProfile(saved);
      setIsEditing(false);
      setError('');
    } catch (err) {
      setError(err.message || 'Could not save your changes. Please try again.');
    }
  };

  const handleAddRole = async (role) => {
    const created = await addPastRole(role);
    setProfile((prev) => ({ ...prev, past_roles: [...prev.past_roles, created] }));
  };

  const handleRemoveRole = async (id) => {
    await removePastRole(id);
    setProfile((prev) => ({ ...prev, past_roles: prev.past_roles.filter((r) => r.id !== id) }));
  };

  if (error && !profile) return <p role="alert">{error}</p>;
  if (!profile) return <p>Loading...</p>;

  return (
    <>
      {error && <p role="alert">{error}</p>}
      {isEditing ? (
        <ProfileEditForm
          profile={profile}
          onSave={handleSave}
          onCancel={() => { setError(''); setIsEditing(false); }}
          onAddRole={handleAddRole}
          onRemoveRole={handleRemoveRole}
        />
      ) : (
        <ProfileView profile={profile} onEdit={() => { setError(''); setIsEditing(true); }} />
      )}
    </>
  );
};

export default Profile;