import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { APP_LANGS, useLang } from '../i18n/LangContext';
import type { AppLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, canViewParent, isPlatformAdmin } from '../lib/api';
import {
  AwardIcon,
  BarChartIcon,
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
  const { t, lang, setLang } = useLang();
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
      <aside className={`sidebar${open ? ' open' : ''}`}>
        <Link to="/dashboard" className="side-brand" onClick={close}>
          <img src="/grandec.png" alt="GRANDEC" className="brand-badge" />
          <span>
            <span className="side-brand-name">GRANDEC</span>
            <span className="side-brand-sub">LMS Platform</span>
          </span>
        </Link>
        <nav className="side-nav">
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
              <NavLink to="/teacher" className={linkClass} onClick={close}><UsersIcon size={16} className="ico" /> {t('students')}</NavLink>
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
              <NavLink to="/panel" className={linkClass} onClick={close}><ShieldCheckIcon size={16} className="ico" /> {t('panel_dashboard')}</NavLink>
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
          <button className="btn ghost sm" onClick={onLogout} title={t('logout')}><LogOutIcon size={14} className="ico" /></button>
        </div>
      </aside>
      {open && <div className="overlay" onClick={close} />}

      <div className="main">
        <header className="topbar app-topbar">
          <div className="topbar-inner">
            <button className="hamburger always" aria-label="Menu" onClick={() => setOpen((v) => !v)}>
              {open ? <XIcon size={20} /> : <MenuIcon size={20} />}
            </button>
            <div className="spacer" />
            <span className="lang-switch" role="group" aria-label="Language">
              {APP_LANGS.map((l: AppLang) => (
                <button
                  key={l}
                  type="button"
                  className={`btn ghost sm${lang === l ? ' active' : ''}`}
                  aria-pressed={lang === l}
                  onClick={() => setLang(l)}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </span>
            {user && <span className={`role role-${user.role}`}>{user.role}</span>}
            <button className="btn ghost sm" onClick={onLogout}>{t('logout')}</button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
