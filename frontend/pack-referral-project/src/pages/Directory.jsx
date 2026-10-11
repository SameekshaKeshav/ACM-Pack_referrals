import SearchBar from '../components/directory/SearchBar';
import FilterSidebar from '../components/directory/FilterSidebar';
import CompanyCard from '../components/directory/CompanyCard';
import PersonCard from '../components/directory/PersonCard';

const Directory = () => {
    return (
        <div>
            <SearchBar />
            <FilterSidebar />
            <CompanyCard />
            <CompanyCard />
            <PersonCard />
            <PersonCard />
        </div>
    )
}

export default Directory; 