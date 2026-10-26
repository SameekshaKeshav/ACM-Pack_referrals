import PastRoleEntry from './PastRoleEntry';

const ProfileView = ({ profile, onEdit }) => {
  return (
    <div>

      <h1>{profile.first_name} {profile.last_name}</h1>
      <p>{profile.major} - Class {profile.grad_year}</p>
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