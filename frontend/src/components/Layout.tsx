import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, canViewParent, isPlatformAdmin } from '../lib/api';
import UserNavDropdown from './UserNavDropdown';
import {
  AwardIcon,
  BarChartIcon,
  CreditCardIcon,
  CrownIcon,
  FileTextIcon,
  FolderOpenIcon,
  GamepadIcon,
  HomeIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MenuIcon,
  PenLineIcon,
  ReceiptIcon,
  ShieldCheckIcon,
  SwordsIcon,
  TrophyIcon,
  UploadIcon,
  UserPlusIcon,
  UsersIcon,
  XIcon,
} from './icons';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `nav-link side-link${isActive ? ' active' : ''}`;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <p className="side-section">{title}</p>
      {children}
    </>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const onLogout = async () => {
    await logout();
    navigate('/login');
  };

  const close = () => setOpen(false);
  const isStudent = user?.role === 'student';
  const isTeacher = canTeach(user);
  const isAdmin = isPlatformAdmin(user);
  const isParent = canViewParent(user);
  const isReviewer = canReviewEssays(user);

  return (
    <div className="app">
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Yon boshqaruv menyusi">
        <Link to="/" className="side-brand" onClick={close} aria-label="GRANDEC LMS Bosh sahifasi">
          <img src="/grandec.png" alt="GRANDEC" className="brand-badge" />
          <span>
            <span className="side-brand-name">GRANDEC</span>
            <span className="side-brand-sub">LMS Platform</span>
          </span>
        </Link>
        <nav className="side-nav" aria-label="Ilova bo'limlari">
          <Section title={t('main')}>
            <NavLink to="/dashboard" className={linkClass} onClick={close}><LayoutDashboardIcon size={16} className="ico" /> {t('dashboard')}</NavLink>
            <NavLink to="/tests" className={linkClass} onClick={close}><FileTextIcon size={16} className="ico" /> {t('tests')}</NavLink>
            {isStudent && (
              <NavLink to="/results" className={linkClass} onClick={close}><TrophyIcon size={16} className="ico" /> {t('my_results')}</NavLink>
            )}
            {isStudent && (
              <NavLink to="/certificates" className={linkClass} onClick={close}><AwardIcon size={16} className="ico" /> {t('my_certificates')}</NavLink>
            )}
            <NavLink to="/games" className={linkClass} onClick={close}><GamepadIcon size={16} className="ico" /> {t('games')}</NavLink>
            <NavLink to="/essays" className={linkClass} onClick={close}><PenLineIcon size={16} className="ico" /> {t('essays')}</NavLink>
            <NavLink to="/arena" className={linkClass} onClick={close}><SwordsIcon size={16} className="ico" /> {t('arena')}</NavLink>
            <NavLink to="/essay-leaderboard" className={linkClass} onClick={close}><AwardIcon size={16} className="ico" /> {t('leaderboard')}</NavLink>
          </Section>
          {isTeacher && (
            <Section title={t('role_teacher')}>
              <NavLink to="/teacher" end className={linkClass} onClick={close}><UsersIcon size={16} className="ico" /> {t('students')}</NavLink>
              <NavLink to="/groups" className={linkClass} onClick={close}><FolderOpenIcon size={16} className="ico" /> {t('groups')}</NavLink>
              <NavLink to="/analytics" className={linkClass} onClick={close}><BarChartIcon size={16} className="ico" /> {t('analytics')}</NavLink>
              <NavLink to="/import" className={linkClass} onClick={close}><UploadIcon size={16} className="ico" /> CSV</NavLink>
              {isReviewer && (
                <NavLink to="/teacher/essays" className={linkClass} onClick={close}><PenLineIcon size={16} className="ico" /> {t('teacher_queue')}</NavLink>
              )}
            </Section>
          )}
          {isAdmin && (
            <Section title={t('panel')}>
              <NavLink to="/panel" end className={linkClass} onClick={close}><ShieldCheckIcon size={16} className="ico" /> {t('panel_dashboard')}</NavLink>
              <NavLink to="/panel/tuition" className={linkClass} onClick={close}><CreditCardIcon size={16} className="ico" /> {t('tuition_title')}</NavLink>
              <NavLink to="/panel/users" className={linkClass} onClick={close}><UserPlusIcon size={16} className="ico" /> {t('manage_teachers')}</NavLink>
            </Section>
          )}
          {isParent && (
            <Section title={t('parent')}>
              <NavLink to="/parent" className={linkClass} onClick={close}><HomeIcon size={16} className="ico" /> {t('children')}</NavLink>
            </Section>
          )}
          <Section title="Premium">
            <NavLink to="/subscribe" className={linkClass} onClick={close}><CrownIcon size={16} className="ico" /> {t('premium')}</NavLink>
            <NavLink to="/my-subscription" className={linkClass} onClick={close}><ReceiptIcon size={16} className="ico" /> {t('pay_current_sub')}</NavLink>
          </Section>
        </nav>
        <div className="side-user">
          <span className="avatar">{(user?.full_name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2) || '?'}</span>
          <span className="side-user-meta">
            <strong>{user?.full_name}</strong>
            <small>{user?.role}</small>
          </span>
          <button className="btn ghost sm" onClick={onLogout} title={t('logout')} aria-label={t('logout')}><LogOutIcon size={14} className="ico" /></button>
        </div>
      </aside>
      {open && <div className="overlay" onClick={close} aria-hidden="true" />}

      <div className="main">
        <header className="topbar app-topbar" aria-label="Yuqori panel">
          <div className="topbar-inner">
            <button
              className="hamburger always"
              aria-label={open ? "Menyuni yopish" : "Menyuni ochish"}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <XIcon size={20} /> : <MenuIcon size={20} />}
            </button>
            <div className="spacer" />
            <UserNavDropdown />
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
