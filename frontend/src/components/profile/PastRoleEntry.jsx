function formatMonthYear(iso) {
  if (!iso) return '';
  const [year, month] = iso.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

const PastRoleEntry = ({ role }) => (
  <div className="role-row">
    <span className="role-company">{role.company}</span>
    <span className="role-title">{role.role_title}</span>
    <span className="role-dates">
      {`${formatMonthYear(role.start_date)} - ${role.end_date ? formatMonthYear(role.end_date) : 'Present'}`}
    </span>
  </div>
);

export default PastRoleEntry;