import { useRef, useState } from 'react';
import PastRoleEntry from './PastRoleEntry';

const EMPTY_ROLE = { company: '', role_title: '', start_date: '', end_date: '' };

const ProfileEditForm = ({ profile, onSave, onCancel, onAddRole, onRemoveRole }) => {
  const [form, setForm] = useState(profile);
  const [newRole, setNewRole] = useState(EMPTY_ROLE);
  const [roleError, setRoleError] = useState('');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const runRoleRequest = async (request) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await request();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value });
  };

  const handleRoleField = (field, value) => {
    setNewRole({ ...newRole, [field]: value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...form,
      grad_year: form.grad_year === '' || form.grad_year == null ? null : Number(form.grad_year),
    });
  };

  const handleAddRole = () => runRoleRequest(async () => {
    const company = newRole.company.trim();
    const role_title = newRole.role_title.trim();
    if (!company || !role_title || !newRole.start_date) {
      setRoleError('Company, role and start date are required.');
      return;
    }
    if (newRole.end_date && newRole.end_date < newRole.start_date) {
      setRoleError('The end date cannot be before the start date.');
      return;
    }
    try {
      await onAddRole({ ...newRole, company, role_title });
      setNewRole(EMPTY_ROLE);
      setRoleError('');
    } catch (err) {
      setRoleError(err.message || 'Could not add the role. Please try again.');
    }
  });

  const handleRemoveRole = (id) => runRoleRequest(async () => {
    try {
      await onRemoveRole(id);
      setRoleError('');
    } catch (err) {
      setRoleError(err.message || 'Could not remove the role. Please try again.');
    }
  });

  // Enter inside the Add a Role fields adds the role instead of saving the whole form.
  const handleRoleKeyDown = (e) => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
      e.preventDefault();
      handleAddRole();
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h1>Edit profile</h1>
      <label>
        First name
        <input value={form.first_name} onChange={(e) => handleChange('first_name', e.target.value)} />
      </label>

      <label>
        Last name
        <input value={form.last_name} onChange={(e) => handleChange('last_name', e.target.value)} />
      </label>

      <label>
        Major
        <input value={form.major} onChange={(e) => handleChange('major', e.target.value)} />
      </label>

      <label>
        Graduation Year
        <input
          type="number"
          value={form.grad_year}
          onChange={(e) => handleChange('grad_year', e.target.value)}
        />
      </label>

      <label>
        Current role
        <input value={form.current_role} onChange={(e) => handleChange('current_role', e.target.value)} />
      </label>

      <label>
        Current company
        <input
          value={form.current_company}
          onChange={(e) => handleChange('current_company', e.target.value)}
        />
      </label>

      <label>
        About
        <textarea value={form.bio} onChange={(e) => handleChange('bio', e.target.value)} />
      </label>

      <label>
        <input
          type="checkbox"
          checked={form.open_to_connect}
          onChange={(e) => handleChange('open_to_connect', e.target.checked)}
        />
        Open to connect
      </label>

      <h2>Job Roles</h2>
      <p>Roles save as you add or remove them. Cancel does not undo them.</p>
      {profile.past_roles.map((role) => (
        <div key={role.id}>
          <PastRoleEntry role={role} />
          <button
            type="button"
            aria-label={`Remove ${role.company} ${role.role_title}`}
            onClick={() => handleRemoveRole(role.id)}
            disabled={busy}
          >
            Remove
          </button>
        </div>
      ))}

      <h3>Add a Role</h3>
      <div>
        <label>
          Company
          <input
            value={newRole.company}
            onChange={(e) => handleRoleField('company', e.target.value)}
            onKeyDown={handleRoleKeyDown}
          />
        </label>
        <label>
          Role title
          <input
            value={newRole.role_title}
            onChange={(e) => handleRoleField('role_title', e.target.value)}
            onKeyDown={handleRoleKeyDown}
          />
        </label>
        <label>
          Start date
          <input
            type="date"
            value={newRole.start_date}
            onChange={(e) => handleRoleField('start_date', e.target.value)}
            onKeyDown={handleRoleKeyDown}
          />
        </label>
        <label>
          End date (leave blank if ongoing)
          <input
            type="date"
            value={newRole.end_date}
            onChange={(e) => handleRoleField('end_date', e.target.value)}
            onKeyDown={handleRoleKeyDown}
          />
        </label>
        <button type="button" onClick={handleAddRole} disabled={busy}>Add role</button>
      </div>
      {roleError && <p role="alert">{roleError}</p>}

      <div>
        <button type="button" onClick={onCancel}>Cancel</button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
};

export default ProfileEditForm;