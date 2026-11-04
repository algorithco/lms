import { NavLink } from 'react-router-dom';
import { FileText, Home, PenLine, Swords, User } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';

interface MobileBottomBarProps {
  onOpenProfile?: () => void;
}

/** Phone navigation: five equal items, ~56 px + safe area, one active colour on every page. */
export default function MobileBottomBar({ onOpenProfile }: MobileBottomBarProps) {
  const { user, openAuthModal } = useAuth();
  const { t } = useLang();

  const onProfile = (e: React.MouseEvent) => {
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

  const items = [
    { to: user ? '/dashboard' : '/', label: t('bnav_home'), Icon: Home, end: true },
    { to: '/essays', label: t('bnav_essays'), Icon: PenLine },
    { to: '/tests', label: t('bnav_tests'), Icon: FileText },
    { to: '/arena', label: t('bnav_arena'), Icon: Swords },
  ];

  return (
    <nav className="bnav" aria-label={t('bnav_label')}>
      {items.map(({ to, label, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `bnav__item${isActive ? ' is-on' : ''}`}>
          <Icon size={22} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
      <NavLink to="/profile" onClick={onProfile} className={({ isActive }) => `bnav__item${isActive ? ' is-on' : ''}`}>
        <User size={22} aria-hidden="true" />
        <span>{t('bnav_profile')}</span>
      </NavLink>
    </nav>
  );
}
