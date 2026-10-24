import { Link, Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom';
import { RequireAuth, useAuth } from './auth/AuthProvider';
import { EmailPage, EnterCodePage } from './pages/Auth';
import Chat from './pages/Chat';
import ChatMockPage from './ChatMockPage';
import Profile from './pages/Profile';
import Directory from './pages/Directory';
import Company from './pages/Company';

function AppLayout() {
  const { user, logout } = useAuth();
  return <><header className="site-header authenticated-header"><Link className="brand" to="/chat"><span className="brand-mark">PR</span>Pack Referrals</Link>
    <nav aria-label="Main navigation"><NavLink to="/chat">Messages</NavLink><NavLink to="/directory">Directory</NavLink><NavLink to="/profile">Profile</NavLink></nav>
    <span className="signed-in-email">{user.email}</span><button className="button-secondary" onClick={logout}>Log out</button></header><Outlet /></>;
}

export default function App() {
  return <Routes>
    <Route path="/signup" element={<EmailPage key="signup" mode="signup" />} />
    <Route path="/login" element={<EmailPage key="login" mode="login" />} />
    <Route path="/enter-code" element={<EnterCodePage />} />
    <Route element={<RequireAuth />}>
      <Route element={<AppLayout />}>
        <Route path="/chat" element={<Chat />} /><Route path="/chat/:conversationId" element={<Chat />} />
        <Route path="/profile" element={<Profile />} /><Route path="/directory" element={<Directory />} /><Route path="/company/:id" element={<Company />} />
      </Route>
      <Route path="/chat-mock" element={<ChatMockPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/chat" replace />} />
  </Routes>;
}
