import PastRoleEntry from './PastRoleEntry';

const ProfileView = ({ profile, onEdit }) => {
  return (
    <div>

      <h1>{profile.name}</h1>
      <p>{profile.major} - Class {profile.grad_year}</p>
      <p>Open to connect: {profile.open_to_connect ? 'On' : 'Off'}</p>
      <button onClick={onEdit}>Edit Profile</button>

      <h2>About</h2>
      <p>{profile.bio}</p>

      <h2>Job Roles</h2>
      {profile.past_roles.map((role, index) => (
        <PastRoleEntry key={index} role={role} />
      ))}

    </div>
  );
};

export default ProfileView;