import { useState } from 'react';
import ProfileView from '../components/profile/ProfileView';
import ProfileEditForm from '../components/profile/ProfileEditForm';

const initialProfile = {
    name: 'Jane Doe',
    major: 'Computer Science',
    grad_year: 2028,
    bio: 'Sophomore interested in backend development and cloud infrastructure.',
    open_to_connect: true,
    past_roles: [
        { company: 'Google', role_title: 'Software Engineering Intern', start_date: '2025-05', end_date: '2025-08' },
        { company: 'Red Hat', role_title: 'Co-op', start_date: '2024-01', end_date: '' },
    ],
};

const Profile = () => {

    const [profile, setProfile] = useState(initialProfile);
    const [isEditing, setIsEditing] = useState(false);

    const handleSave = (updatedProfile) => {
    console.log('Saving profile:', updatedProfile);
    setProfile(updatedProfile);
    setIsEditing(false);
    };



    return isEditing ? (
        <ProfileEditForm
            profile={profile}
            onSave={handleSave}
            onCancel={() => setIsEditing(false)}
        />
    ) : (
        <ProfileView profile={profile} onEdit={() => setIsEditing(true)} />
    );

};

export default Profile; 
