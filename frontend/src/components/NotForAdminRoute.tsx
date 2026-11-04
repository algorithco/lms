import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isPlatformAdmin } from '../lib/api';

/** Plans and checkout are for students and teachers; an administrator is unlimited and goes to the panel. */
export default function NotForAdminRoute() {
  const { user } = useAuth();
  if (user && isPlatformAdmin(user)) return <Navigate to="/panel" replace />;
  return <Outlet />;
}
