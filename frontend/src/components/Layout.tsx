import { useState, useEffect } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, canViewParent, isPlatformAdmin, GamificationApi, type StreakInfoResponse } from '../lib/api';
import UserNavDropdown from './UserNavDropdown';
import SubjectSwitcher from './SubjectSwitcher';
import {
  AwardIcon,
  BarChartIcon,
  CameraIcon,
  CreditCardIcon,
  CrownIcon,
  FileTextIcon,
  FlameIcon,
  FolderOpenIcon,
  GamepadIcon,
  HomeIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MenuIcon,
  MicIcon,
  PenLineIcon,
  ReceiptIcon,
  ShieldCheckIcon,
  SwordsIcon,
  TrophyIcon,
  UploadIcon,
  UserPlusIcon,
  UsersIcon,
  ZapIcon,
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
  const [streakData, setStreakData] = useState<StreakInfoResponse | null>(null);
  const [activeSubject, setActiveSubject] = useState<'uzbek' | 'english'>(() => {
    return (user?.active_subject as 'uzbek' | 'english') ||
      (localStorage.getItem('lms_subject') as 'uzbek' | 'english') ||
      'uzbek';
  });

  useEffect(() => {
    if (user?.active_subject) {
      setActiveSubject(user.active_subject as 'uzbek' | 'english');
    }
  }, [user?.active_subject]);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<'uzbek' | 'english'>;
      const next = customEvent.detail || (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
      setActiveSubject(next);
    };
    window.addEventListener('subject-changed', handler);
    return () => window.removeEventListener('subject-changed', handler);
  }, []);

  useEffect(() => {
    if (!user) return;
    GamificationApi.streak()
      .then((res) => setStreakData(res))
      .catch(() => {});
  }, [user]);

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
            {activeSubject === 'english' ? (
              <>
                <NavLink to="/tests" className={linkClass} onClick={close}>
                  <FileTextIcon size={16} className="ico" /> CBT Reading & Listening
                </NavLink>
                <NavLink to="/speaking" className={linkClass} onClick={close}>
                  <MicIcon size={16} className="ico" /> AI Speaking (IELTS & Multi-level)
                </NavLink>
                <NavLink to="/essays" className={linkClass} onClick={close}>
                  <PenLineIcon size={16} className="ico" /> IELTS Writing
                </NavLink>
              </>
            ) : (
              <>
                <NavLink to="/tests" className={linkClass} onClick={close}>
                  <FileTextIcon size={16} className="ico" /> {t('tests')}
                </NavLink>
                <NavLink to="/tests/scan-omr" className={linkClass} onClick={close}>
                  <CameraIcon size={16} className="ico" /> Titul (OMR)
                </NavLink>
                <NavLink to="/essays" className={linkClass} onClick={close}>
                  <PenLineIcon size={16} className="ico" /> {t('essays')}
                </NavLink>
              </>
            )}
            {isStudent && (
              <NavLink to="/results" className={linkClass} onClick={close}><TrophyIcon size={16} className="ico" /> {t('my_results')}</NavLink>
            )}
            {isStudent && (
              <NavLink to="/certificates" className={linkClass} onClick={close}><AwardIcon size={16} className="ico" /> {t('my_certificates')}</NavLink>
            )}
            {activeSubject === 'uzbek' && (
              <NavLink to="/games" className={linkClass} onClick={close}><GamepadIcon size={16} className="ico" /> {t('games')}</NavLink>
            )}
            <NavLink to="/arena" className={linkClass} onClick={close}>
              <SwordsIcon size={16} className="ico" /> {activeSubject === 'english' ? 'Vocabulary Arena' : t('arena')}
            </NavLink>
            <NavLink to="/tournaments" className={linkClass} onClick={close}><TrophyIcon size={16} className="ico" /> Turnirlar</NavLink>
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
          {(isAdmin || isTeacher || user?.role === 'center_admin') && (
            <Section title="Enterprise">
              <NavLink to="/enterprise" className={linkClass} onClick={close}><ShieldCheckIcon size={16} className="ico" /> O'quv markazi</NavLink>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {streakData && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: '20px',
                    background: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    fontSize: '12px',
                    fontWeight: 700,
                    color: '#f59e0b',
                  }}
                  title={`Ketma-ketlik (Streak): ${streakData.current_streak} kun | Jami: ${streakData.xp_points} XP`}
                >
                  <FlameIcon size={14} style={{ color: streakData.is_active_today ? '#ea580c' : '#f59e0b' }} />
                  <span>{streakData.current_streak}</span>
                  <span style={{ opacity: 0.4 }}>•</span>
                  <ZapIcon size={12} style={{ color: '#fbbf24' }} />
                  <span>{streakData.xp_points} XP</span>
                </div>
              )}
              <SubjectSwitcher size="sm" />
              {isAdmin && (
                <Link
                  to="/panel"
                  className="topbar-admin-pill"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '5px 12px',
                    borderRadius: '8px',
                    background: 'rgba(245, 158, 11, 0.15)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    color: '#f59e0b',
                    fontWeight: 700,
                    fontSize: '12px',
                    textDecoration: 'none',
                    transition: 'all 0.2s ease',
                  }}
                  title="Admin Boshqaruv Paneli"
                >
                  <ShieldCheckIcon size={14} />
                  <span className="hidden sm:inline">Admin Panel</span>
                </Link>
              )}
              <UserNavDropdown />
            </div>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
