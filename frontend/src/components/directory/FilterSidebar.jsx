// Majors offered as checkboxes. The directory matches a major by substring, so these
// are search terms, not a closed list: a member whose major is stored as free text
// still matches when it contains one of them.
export const MAJOR_OPTIONS = [
  'Computer Science',
  'Computer Engineering',
  'Electrical Engineering',
  'Mechanical Engineering',
  'Industrial Engineering',
  'Data Science',
  'Statistics',
  'Mathematics',
  'Business Administration',
];

export function gradYearOptions(now = new Date()) {
  const year = now.getFullYear();
  return Array.from({ length: 9 }, (_, index) => year - 2 + index);
}

const FilterSidebar = ({ majors, gradYear, onMajorsChange, onGradYearChange, onClear }) => {
  const toggle = (major) => onMajorsChange(
    majors.includes(major) ? majors.filter((value) => value !== major) : [...majors, major],
  );
  const filtering = majors.length > 0 || gradYear !== '';

  return (
    <form className="filter-sidebar" aria-label="Filter members" onSubmit={(event) => event.preventDefault()}>
      <fieldset className="filter-group">
        <legend>Major</legend>
        {MAJOR_OPTIONS.map((major) => (
          <label key={major} className="filter-check">
            <input type="checkbox" checked={majors.includes(major)} onChange={() => toggle(major)} />
            <span>{major}</span>
          </label>
        ))}
      </fieldset>

      <div className="filter-group">
        <label htmlFor="filter-grad-year">Graduation year</label>
        <select id="filter-grad-year" value={gradYear} onChange={(event) => onGradYearChange(event.target.value)}>
          <option value="">Any year</option>
          {gradYearOptions().map((year) => <option key={year} value={String(year)}>{year}</option>)}
        </select>
      </div>

      <button type="button" className="button-secondary" onClick={onClear} disabled={!filtering}>Clear filters</button>
    </form>
  );
};

export default FilterSidebar;
