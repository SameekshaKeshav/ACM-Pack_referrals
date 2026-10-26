import { useParams } from 'react-router-dom';
const Company = () => {

    {/* useParam reads the :id from the URL */}
    const { id } = useParams();

    return (
        <div>Company {id}</div>
    )
}

export default Company;