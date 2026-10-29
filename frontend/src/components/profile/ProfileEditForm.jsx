import { useState } from 'react';
import PastRoleEntry from './PastRoleEntry';

const ProfileEditForm = ({ profile, onSave, onCancel }) => {
  const [form, setForm] = useState(profile);

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
    ...form,
    grad_year: form.grad_year === '' || form.grad_year == null ? null : Number(form.grad_year),
    });

  };

  return (
    <form onSubmit={handleSubmit}>
      <label>
        First name
        <input
          value={form.first_name}
          onChange={(e) => handleChange('first_name', e.target.value)}
        />
      </label>

      <label>
        Last name
        <input
          value={form.last_name}
          onChange={(e) => handleChange('last_name', e.target.value)}
        />
      </label>

      <label>
        Major
        <input
          value={form.major}
          onChange={(e) => handleChange('major', e.target.value)}
        />
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
        About
        <textarea
          value={form.bio}
          onChange={(e) => handleChange('bio', e.target.value)}
        />
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
      {form.past_roles.map((role) => (
        <PastRoleEntry key={role.id} role={role} />
      ))}
      <p>Editing roles is coming in the next update.</p>

      <div>
        <button type="button" onClick={onCancel}>Cancel</button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
};

export default ProfileEditForm;