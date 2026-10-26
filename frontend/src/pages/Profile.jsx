import { useState, useEffect } from 'react';
import ProfileView from '../components/profile/ProfileView';
import ProfileEditForm from '../components/profile/ProfileEditForm';
import { getMyProfile, updateMyProfile } from '../api/profile';

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

  if (error && !profile) return <p role="alert">{error}</p>;
  if (!profile) return <p>Loading...</p>;

  return (
    <>
      {error && <p role="alert">{error}</p>}
      {isEditing ? (
        <ProfileEditForm
          profile={profile}
          onSave={handleSave}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <ProfileView profile={profile} onEdit={() => setIsEditing(true)} />
      )}
    </>
  );
};

export default Profile;