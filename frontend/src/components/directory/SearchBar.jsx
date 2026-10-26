// Controlled search box. The page owns the text and does the fetching.
const SearchBar = ({ value, onChange }) => (
  <form className="company-search" role="search" aria-label="Search companies" onSubmit={(event) => event.preventDefault()}>
    <label htmlFor="company-search">Search companies</label>
    <input
      id="company-search"
      type="search"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Try Google, Microsoft, Acme…"
      autoComplete="off"
    />
  </form>
);

export default SearchBar;
