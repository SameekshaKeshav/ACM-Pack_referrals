import PastRoleEntry from './PastRoleEntry';

const ProfileView = ({ profile, onEdit }) => {

  const summary = [
    profile.major,
    profile.grad_year ? `Class ${profile.grad_year}` : '',
  ].filter(Boolean).join(' - ');
  
  return (
    <div>

      <h1>{profile.first_name} {profile.last_name}</h1>
      <p>{summary}</p>
      <p>Open to connect: {profile.open_to_connect ? 'On' : 'Off'}</p>
      <button onClick={onEdit}>Edit Profile</button>

      <h2>About</h2>
      <p>{profile.bio}</p>

      <h2>Job Roles</h2>
      {profile.past_roles.map((role) => (
        <PastRoleEntry key={role.id} role={role} />
      ))}

    </div>
  );
};

export default ProfileView;