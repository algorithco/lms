import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isPlatformAdmin } from '../lib/api';
import Dashboard from './Dashboard';
import TeacherDashboard from './TeacherDashboard';

export default function DashboardRouter() {
  const { user, loading } = useAuth();

  if (loading) {
    return <p className="route-loading" role="status">Yuklanmoqda…</p>;
  }

  // 1. Admins & Center Admins route directly to the Admin Control Panel
  if (isPlatformAdmin(user) || user?.role === 'center_admin') {
    return <Navigate to="/panel" replace />;
  }

  // 2. Teachers get the dedicated Teacher Dashboard (O'qituvchi Kabineti)
  if (user?.role === 'teacher') {
    return <TeacherDashboard />;
  }

  // 3. Students get the standard Student Dashboard
  return <Dashboard />;
}
