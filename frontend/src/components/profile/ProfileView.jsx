import PastRoleEntry from './PastRoleEntry';

function initialsFor(profile) {
  const letters = [profile.first_name, profile.last_name]
    .map((name) => (name || '').trim()[0])
    .filter(Boolean)
    .join('');
  return (letters || (profile.email || '').trim()[0] || '?').toUpperCase();
}

const ProfileView = ({ profile, onEdit }) => {
  const displayName =
  [profile.first_name, profile.last_name].filter(Boolean).join(' ') ||
  profile.email ||
  'Your profile';

  const summary = [
    profile.major,
    profile.grad_year ? `Class ${profile.grad_year}` : '',
  ].filter(Boolean).join(' - ');

  const job = [profile.current_role, profile.current_company].filter(Boolean).join(' at ');

  return (
    <div className="main-content profile-page">
      <div className="profile-layout">
        <aside className="profile-side">
          <div className="profile-avatar" aria-hidden="true">{initialsFor(profile)}</div>
          <button type="button" className="button-primary" onClick={onEdit}>Edit Profile</button>
          <div className="connect-row">
            <span>Open to connect</span>
            <span className="connect-state">
              <span className={`switch${profile.open_to_connect ? ' switch-on' : ''}`} aria-hidden="true" />
              {profile.open_to_connect ? 'On' : 'Off'}
            </span>
          </div>
        </aside>

        <div className="profile-main">
          <h1>{displayName}</h1>
          {summary && <p className="profile-summary">{summary}</p>}
          {job && <p className="profile-job">{job}</p>}

          <section className="profile-card" aria-labelledby="about-heading">
            <h2 id="about-heading">About</h2>
            <p>{profile.bio || 'No bio yet.'}</p>
          </section>

          <section className="profile-roles" aria-labelledby="roles-heading">
            <h2 id="roles-heading">Job Roles</h2>
            {profile.past_roles.length === 0 ? (
              <p className="empty-note">No roles added yet.</p>
            ) : (
              <div className="role-list">
                {profile.past_roles.map((role) => (
                  <PastRoleEntry key={role.id} role={role} />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

export default ProfileView;