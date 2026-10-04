import {BrowserRouter, Route, Routes} from 'react-router-dom';
import Profile from './pages/Profile';
import Directory from './pages/Directory';
import Company from './pages/Company';
import NotFound from './pages/NotFound';

const App = () => {
    return (
        <div className="App">
        <BrowserRouter>
        <Routes>
            <Route path='/' element={<Profile/>}/>
            <Route path='/directory' element={<Directory/>}/>
            <Route path='/about' element={<Company/>}/>
            <Route path='*' element={<NotFound/>}/>
        </Routes>
        </BrowserRouter>
        </div>
    )
}

export default App
