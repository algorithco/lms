import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../theme/ThemeContext';
import {
  FileTextIcon,
  HomeIcon,
  PenLineIcon,
  SwordsIcon,
  UserIcon,
} from './icons';

interface MobileBottomBarProps {
  onOpenProfile?: () => void;
}

export default function MobileBottomBar({ onOpenProfile }: MobileBottomBarProps) {
  const { user, openAuthModal } = useAuth();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const handleProfileClick = (e: React.MouseEvent) => {
    if (onOpenProfile) {
      e.preventDefault();
      onOpenProfile();
      return;
    }
    if (!user) {
      e.preventDefault();
      openAuthModal('login');
    }
  };

  return (
    <nav
      className="testmakon-bottom-bar md:hidden fixed bottom-0 left-0 right-0 z-50"
      aria-label="Mobil pastki navigatsiya"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        height: 'calc(62px + env(safe-area-inset-bottom, 0px))',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        background: isDark ? 'rgba(15, 23, 42, 0.94)' : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.9)',
        boxShadow: isDark
          ? '0 -6px 25px rgba(0, 0, 0, 0.45)'
          : '0 -6px 25px rgba(15, 23, 42, 0.08)',
        alignItems: 'center',
        justifyContent: 'space-around',
        paddingLeft: '12px',
        paddingRight: '12px',
      }}
    >
      {/* 1. BOSH SAHIFA */}
      <NavLink
        to={user ? '/dashboard' : '/'}
        end
        className={({ isActive }) => `testmakon-nav-item ${isActive ? 'active' : ''}`}
      >
        {({ isActive }) => (
          <>
            <div className={`testmakon-icon-wrap ${isActive ? 'active' : ''}`}>
              <HomeIcon size={20} />
            </div>
            <span className="testmakon-label">Bosh</span>
          </>
        )}
      </NavLink>

      {/* 2. AI ESSE */}
      <NavLink
        to="/essays"
        className={({ isActive }) => `testmakon-nav-item ${isActive ? 'active' : ''}`}
      >
        {({ isActive }) => (
          <>
            <div className={`testmakon-icon-wrap ${isActive ? 'active' : ''}`}>
              <PenLineIcon size={20} />
            </div>
            <span className="testmakon-label">AI Esse</span>
          </>
        )}
      </NavLink>

      {/* 3. TESTLAR (CENTER RAISED 3D ACTION BUTTON) */}
      <NavLink
        to="/tests"
        className={({ isActive }) => `testmakon-center-item ${isActive ? 'active' : ''}`}
      >
        {({ isActive }) => (
          <div className="testmakon-raised-wrapper">
            <div className={`testmakon-raised-pill ${isActive ? 'active' : ''}`}>
              <FileTextIcon size={22} />
            </div>
            <span className={`testmakon-label-center ${isActive ? 'active' : ''}`}>Testlar</span>
          </div>
        )}
      </NavLink>

      {/* 4. ARENA (1v1) */}
      <NavLink
        to="/arena"
        className={({ isActive }) => `testmakon-nav-item ${isActive ? 'active' : ''}`}
      >
        {({ isActive }) => (
          <>
            <div className={`testmakon-icon-wrap ${isActive ? 'active' : ''}`}>
              <SwordsIcon size={20} />
            </div>
            <span className="testmakon-label">Arena</span>
          </>
        )}
      </NavLink>

      {/* 5. PROFIL */}
      <NavLink
        to="/profile"
        onClick={handleProfileClick}
        className={({ isActive }) => `testmakon-nav-item ${isActive ? 'active' : ''}`}
      >
        {({ isActive }) => (
          <>
            <div className={`testmakon-icon-wrap ${isActive ? 'active' : ''}`}>
              <UserIcon size={20} />
            </div>
            <span className="testmakon-label">Profil</span>
          </>
        )}
      </NavLink>
    </nav>
  );
}
