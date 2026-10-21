const PastRoleEntry = ({ role, editable = false, onChange, onRemove }) => {

  if (!editable) {
    return (
      <div>
        {role.company} · {role.role_title} ({role.start_date} - {role.end_date || 'Present'})
      </div>
    );
  }

  return (
    <div>
      <input
        value={role.company}
        onChange={(e) => onChange('company', e.target.value)}
        placeholder="Company"
      />
      <input
        value={role.role_title}
        onChange={(e) => onChange('role_title', e.target.value)}
        placeholder="Position"
      />
      <input
        type="month"
        value={role.start_date}
        onChange={(e) => onChange('start_date', e.target.value)}
      />
      <input
        type="month"
        value={role.end_date}
        onChange={(e) => onChange('end_date', e.target.value)}
      />
      <button type="button" onClick={onRemove}>Remove</button>
    </div>
  );

};

export default PastRoleEntry;