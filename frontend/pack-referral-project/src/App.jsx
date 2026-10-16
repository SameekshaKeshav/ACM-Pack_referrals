import {BrowserRouter, Route, Routes, Link, Navigate} from 'react-router-dom';
import Profile from './pages/Profile';
import Directory from './pages/Directory';
import Company from './pages/Company';
import NotFound from './pages/NotFound';

const App = () => {
    return (
        <div className="App">
        <BrowserRouter>
            <nav style={{ display: 'flex', gap: '16px', padding: '12px' }}>
                <Link to="/profile">Profile</Link>
                <Link to="/directory">Directory</Link>

                {/* The /company/1 is just a temporary path, so the link has somewhere to go. */}
                <Link to="/company/1">Company</Link>
            </nav>

            
            <Routes>
                {/* You can change this with a landing page later. */}
                <Route path="/" element={<Navigate to="/profile" replace/>} />
                
                <Route path='/profile' element={<Profile/>} />
                <Route path='/directory' element={<Directory/>} />
                <Route path='/company/:id' element={<Company/>} />
                <Route path='*' element={<NotFound/>} />
                </Routes>
        </BrowserRouter>
        </div>
    )
}

export default App
