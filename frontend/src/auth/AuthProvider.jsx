import { createContext, useContext, useSyncExternalStore } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { getSession, subscribeSession, signOut } from './session';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const session = useSyncExternalStore(subscribeSession, getSession, () => null);
  return <AuthContext.Provider value={{ session, user: session?.user, logout: signOut }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);

export function RequireAuth() {
  const { session } = useAuth();
  const location = useLocation();
  return session ? <Outlet key={session.user.id} /> : <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />;
}
