import { useState } from 'react';
import PastRoleEntry from './PastRoleEntry';

const ProfileEditForm = ({ profile, onSave, onCancel }) => {
  const [form, setForm] = useState(profile);

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value });
  };

  const handleRoleChange = (index, field, value) => {
    const updatedRoles = form.past_roles.map((role, i) =>
      i === index ? { ...role, [field]: value } : role
    );
    setForm({ ...form, past_roles: updatedRoles });
  };

  const addRole = () => {
    setForm({
      ...form,
      past_roles: [
        ...form.past_roles,
        { company: '', role_title: '', start_date: '', end_date: '' },
      ],
    });
  };

  const removeRole = (index) => {
    setForm({
      ...form,
      past_roles: form.past_roles.filter((_, i) => i !== index),
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({ ...form, grad_year: Number(form.grad_year) });
  };

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Name
        <input
          value={form.name}
          onChange={(e) => handleChange('name', e.target.value)}
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

      <h2>Roles</h2>
      {form.past_roles.map((role, index) => (
        <PastRoleEntry
          key={index}
          role={role}
          editable
          onChange={(field, value) => handleRoleChange(index, field, value)}
          onRemove={() => removeRole(index)}
        />
      ))}
      <button type="button" onClick={addRole}>+ Add a Role</button>

      <div>
        <button type="button" onClick={onCancel}>Cancel</button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
};

export default ProfileEditForm;