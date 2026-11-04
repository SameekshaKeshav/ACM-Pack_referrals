function formatMonthYear(iso) {
  if (!iso) return '';
  const [year, month] = iso.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

const PastRoleEntry = ({ role, editable = false, onChange, onRemove }) => {

  if (!editable) {
    return (
      <div>
        {role.company} · {role.role_title} ({formatMonthYear(role.start_date)} - {role.end_date ? formatMonthYear(role.end_date) : 'Present'})
      </div>
    );
  }

  return (
    <div>
      <input
        aria-label="Company"
        value={role.company}
        onChange={(e) => onChange('company', e.target.value)}
        placeholder="Company"
      />
      <input
        aria-label="Position"
        value={role.role_title}
        onChange={(e) => onChange('role_title', e.target.value)}
        placeholder="Position"
      />
      <input
        aria-label="Role start month"
        type="month"
        value={role.start_date}
        onChange={(e) => onChange('start_date', e.target.value)}
      />
      <input
        aria-label="Role end month"
        type="month"
        value={role.end_date}
        onChange={(e) => onChange('end_date', e.target.value)}
      />
      <button type="button" onClick={onRemove}>Remove</button>
    </div>
  );

};

export default PastRoleEntry;