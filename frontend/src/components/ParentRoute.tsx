import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { canViewParent } from '../lib/api';

export default function ParentRoute() {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading session…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!canViewParent(user)) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
