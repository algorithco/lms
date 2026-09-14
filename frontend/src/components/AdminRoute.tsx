import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isPlatformAdmin } from '../lib/api';

export default function AdminRoute() {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading session…</p>;
  if (!user) return <Navigate to="/login" replace />;
  // Platform admin = superuser or role==admin (mirrors IsPanelAdmin).
  // A superuser with role==student still passes — role alone is not the rule.
  if (!isPlatformAdmin(user)) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
