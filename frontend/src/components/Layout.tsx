import { useState, useEffect } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, canViewParent, isPlatformAdmin, GamificationApi, type StreakInfoResponse } from '../lib/api';
import UserNavDropdown from './UserNavDropdown';
import MobileBottomBar from './MobileBottomBar';
import MobileNavDrawer from './MobileNavDrawer';
import MobileProfileDrawer from './MobileProfileDrawer';
import SubjectSwitcher from './SubjectSwitcher';
import {
  BarChartIcon,
  CameraIcon,
  CreditCardIcon,
  CrownIcon,
  FileTextIcon,
  FlameIcon,
  FolderOpenIcon,
  HomeIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MenuIcon,
  MicIcon,
  PenLineIcon,
  ShieldCheckIcon,
  SparklesIcon,
  SwordsIcon,
  TrophyIcon,
  UploadIcon,
  UserPlusIcon,
  UsersIcon,
  ZapIcon,
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
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const [profileDrawerOpen, setProfileDrawerOpen] = useState(false);
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
  const isTeacher = canTeach(user);
  const isAdmin = isPlatformAdmin(user);
  const isParent = canViewParent(user);
  const isReviewer = canReviewEssays(user);

  return (
    <div className="app">
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Yon boshqaruv menyusi">
        <Link to="/" className="side-brand" onClick={close} aria-label="GRANDEC LMS Bosh sahifasi">
          <img src="/logo-mark.png" alt="GRANDEC" className="brand-badge" style={{ height: 38, width: 'auto', background: 'transparent' }} />
          <span>
            <span className="side-brand-name">GRANDEC</span>
            <span className="side-brand-sub" style={{ color: '#D97706', fontWeight: 700, fontSize: '9px', letterSpacing: '0.12em' }}>ACADEMIC EDTECH</span>
          </span>
        </Link>
        <nav className="side-nav" aria-label="Ilova bo'limlari">
          {/* Admin Dedicated Section */}
          {isAdmin && (
            <Section title={t('panel', 'Tizim Boshqaruvi')}>
              <NavLink to="/panel" end className={linkClass} onClick={close}>
                <ShieldCheckIcon size={16} className="ico" /> {t('panel_dashboard', 'Tizim Statistikasi')}
              </NavLink>
              <NavLink to="/panel/tuition" className={linkClass} onClick={close}>
                <CreditCardIcon size={16} className="ico" /> {t('tuition_title', 'To‘lov Cheklari')}
              </NavLink>
              <NavLink to="/panel/users" className={linkClass} onClick={close}>
                <UserPlusIcon size={16} className="ico" /> {t('manage_teachers', 'O‘qituvchilarni Boshqarish')}
              </NavLink>
              <NavLink to="/panel/tests" className={linkClass} onClick={close}>
                <FileTextIcon size={16} className="ico" /> {t('all_tests_control', 'Barcha Testlar Nazorati')}
              </NavLink>
              <NavLink to="/enterprise" className={linkClass} onClick={close}>
                <UsersIcon size={16} className="ico" /> {t('enterprise_title', 'O‘quv Markazlari')}
              </NavLink>
            </Section>
          )}

          {/* Teacher Dedicated Section */}
          {isTeacher && (
            <Section title={t('role_teacher', 'O‘qituvchi Kabineti')}>
              <NavLink to="/dashboard" end className={linkClass} onClick={close}>
                <LayoutDashboardIcon size={16} className="ico" /> {t('teacher_cabinet', 'O‘qituvchi Kabineti')}
              </NavLink>
              <NavLink to="/groups" className={linkClass} onClick={close}>
                <FolderOpenIcon size={16} className="ico" /> {t('my_groups', 'Mening Guruhlarim')}
              </NavLink>
              <NavLink to="/tests/create" className={linkClass} onClick={close}>
                <SparklesIcon size={16} className="ico" /> {t('create_smart_test', 'Yangi Test Yaratish')}
              </NavLink>
              <NavLink to="/tests" className={linkClass} onClick={close}>
                <FileTextIcon size={16} className="ico" /> {t('my_tests', 'Mening Testlarim')}
              </NavLink>
              <NavLink to="/teacher" end className={linkClass} onClick={close}>
                <UsersIcon size={16} className="ico" /> {t('students', 'O‘quvchilar')}
              </NavLink>
              <NavLink to="/teacher/ai-converter" className={linkClass} onClick={close}>
                <SparklesIcon size={16} className="ico" /> AI Test Konvertor
              </NavLink>
              {isReviewer && (
                <NavLink to="/teacher/essays" className={linkClass} onClick={close}>
                  <PenLineIcon size={16} className="ico" /> {t('teacher_queue', 'Esse Tekshiruvi')}
                </NavLink>
              )}
              <NavLink to="/analytics" className={linkClass} onClick={close}>
                <BarChartIcon size={16} className="ico" /> {t('analytics', 'Tahlillar')}
              </NavLink>
              <NavLink to="/import" className={linkClass} onClick={close}>
                <UploadIcon size={16} className="ico" /> CSV Import
              </NavLink>
            </Section>
          )}

          {/* Student & Learning Core Section */}
          <Section title={isTeacher ? t('learning_tools', 'O‘quv Vositalari') : t('main_menu', 'Asosiy Menyu')}>
            {!isTeacher && !isAdmin && (
              <NavLink to="/dashboard" className={linkClass} onClick={close}>
                <LayoutDashboardIcon size={16} className="ico" /> {t('dashboard', 'Boshqaruv paneli')}
              </NavLink>
            )}
            <NavLink to="/tests" className={linkClass} onClick={close}>
              <FileTextIcon size={16} className="ico" /> {t('cbt_tests', 'Testlar (CBT)')}
            </NavLink>
            <NavLink to="/essays" className={linkClass} onClick={close}>
              <PenLineIcon size={16} className="ico" /> {t('ai_essay_studio', 'AI Esse Studiyasi')}
            </NavLink>
            <NavLink to="/arena" className={linkClass} onClick={close}>
              <SwordsIcon size={16} className="ico" /> {t('arena_live_duel', '1v1 Arena (Jonli jang)')}
            </NavLink>
            <NavLink to="/results" className={linkClass} onClick={close}>
              <TrophyIcon size={16} className="ico" /> {t('results_analysis', 'Natijalar va Tahlil')}
            </NavLink>
            <NavLink to="/tests/scan-omr" className={linkClass} onClick={close}>
              <CameraIcon size={16} className="ico" /> {t('titul_scanner', 'Titul (OMR) Skaner')}
            </NavLink>
            {activeSubject === 'english' && (
              <NavLink to="/speaking" className={linkClass} onClick={close}>
                <MicIcon size={16} className="ico" /> AI Speaking
              </NavLink>
            )}
          </Section>

          {isParent && (
            <Section title={t('parent')}>
              <NavLink to="/parent" className={linkClass} onClick={close}><HomeIcon size={16} className="ico" /> {t('children')}</NavLink>
            </Section>
          )}

          {/* Membership Badge / Upgrade Callout */}
          {isAdmin ? (
            <div style={{ margin: '16px 10px 10px', padding: '12px 14px', borderRadius: '16px', background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.15) 0%, rgba(217, 119, 6, 0.1) 100%)', border: '1px solid rgba(168, 85, 247, 0.35)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 16 }}>👑</span>
                <strong style={{ fontSize: 13, color: '#c084fc' }}>Tizim Administratori</strong>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                Root Access: Barcha kvotalar va vositalarga to‘liq cheksiz kirish.
              </p>
            </div>
          ) : user?.is_paid && user?.plan && user?.plan.toUpperCase() !== 'FREE' ? (
            <div style={{ margin: '16px 10px 10px', padding: '12px 14px', borderRadius: '16px', background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.05) 100%)', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <CrownIcon size={16} style={{ color: '#f59e0b' }} />
                <strong style={{ fontSize: 13, color: '#f59e0b' }}>Tarif: {user.plan.toUpperCase()}</strong>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                Faol obuna: cheksiz ta‘lim imkoniyatlari.
              </p>
            </div>
          ) : (
            <div style={{ margin: '16px 10px 10px', padding: '14px', borderRadius: '16px', background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.05) 100%)', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <CrownIcon size={16} style={{ color: '#f59e0b' }} />
                <strong style={{ fontSize: 13, color: '#f59e0b' }}>{t('premium_membership', 'Premium A’zolik')}</strong>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                {t('premium_sub_hint', '12 mezonli BMB esse tekshiruvi va cheksiz CBT testlar.')}
              </p>
              <Link to="/subscribe" className="btn sm primary" onClick={close} style={{ width: '100%', textAlign: 'center', display: 'block', padding: '7px 10px', fontSize: 12, borderRadius: 10, textDecoration: 'none', fontWeight: 800, background: 'linear-gradient(135deg, #f59e0b, #d97706)', border: 'none', color: '#090d16' }}>
                {t('upgrade_tier', 'Tarifni oshirish')} →
              </Link>
            </div>
          )}
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
        <header className="topbar app-topbar backdrop-blur-md" aria-label="Yuqori panel">
          <div className="topbar-inner">
            {/* Mobile-only brand logo (Desktop uses left sidebar brand exclusively) */}
            <div className="topbar-mobile-brand flex md:hidden items-center gap-2">
              <Link to="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
                <img src="/logo-mark.png" alt="GRANDEC" style={{ height: 32, width: 'auto', objectFit: 'contain' }} />
                <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left' }}>
                  <span style={{ fontWeight: 900, fontSize: 14, lineHeight: 1.1, color: 'var(--ink)' }}>GRANDEC</span>
                  <span style={{ fontSize: 8, fontWeight: 800, color: '#D97706', letterSpacing: '0.1em' }}>ACADEMIC EDTECH</span>
                </div>
              </Link>
            </div>

            {/* Desktop Context Badge */}
            <div className="hidden md:flex items-center gap-2">
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 12px',
                  borderRadius: 16,
                  background: 'rgba(245, 158, 11, 0.08)',
                  border: '1px solid rgba(245, 158, 11, 0.2)',
                  fontSize: 12,
                  fontWeight: 700,
                  color: '#B45309',
                }}
              >
                <span>🏛️</span>
                <span>Milliy Sertifikat & AI Esse LMS</span>
              </span>
            </div>
            <div className="spacer" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {streakData && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '4px 8px',
                    borderRadius: '20px',
                    background: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    color: '#f59e0b',
                  }}
                  title={`Ketma-ketlik (Streak): ${streakData.current_streak} kun | Jami: ${streakData.xp_points} XP`}
                >
                  <FlameIcon size={13} style={{ color: streakData.is_active_today ? '#ea580c' : '#f59e0b' }} />
                  <span>{streakData.current_streak}</span>
                  <span style={{ opacity: 0.4 }}>•</span>
                  <ZapIcon size={11} style={{ color: '#fbbf24' }} />
                  <span>{streakData.xp_points} XP</span>
                </div>
              )}
              <SubjectSwitcher size="sm" />
              <div className="hidden md:flex items-center gap-2">
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
                    <span>Admin Panel</span>
                  </Link>
                )}
                <UserNavDropdown />
              </div>

              {/* Mobile Right Controls: Compact Avatar Icon + Hamburger Menu (☰) */}
              <div className="flex md:hidden items-center gap-2">
                <button
                  type="button"
                  onClick={() => setProfileDrawerOpen(true)}
                  aria-label="Profilni ochish"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                    color: '#FFFFFF',
                    border: '2px solid rgba(245, 158, 11, 0.7)',
                    boxShadow: '0 2px 8px rgba(217, 119, 6, 0.3)',
                    cursor: 'pointer',
                    padding: 0,
                    overflow: 'hidden',
                  }}
                >
                  {user?.avatar ? (
                    <img src={user.avatar} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <span style={{ fontSize: 11, fontWeight: 900 }}>
                      {(user?.full_name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase() || 'U'}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setNavDrawerOpen(true)}
                  aria-label="Menyuni ochish"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 34,
                    height: 34,
                    borderRadius: 10,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    color: 'var(--ink)',
                    cursor: 'pointer',
                  }}
                >
                  <MenuIcon size={18} />
                </button>
              </div>
            </div>
          </div>
        </header>
        <main className="content pb-28 md:pb-8">
          <Outlet />
        </main>
      </div>

      {/* TESTMAKON-STYLE 3D SOFT BOTTOM NAVIGATION & DRAWERS */}
      <div className="md:hidden"><MobileBottomBar onOpenProfile={() => setProfileDrawerOpen(true)} /></div>
      <MobileNavDrawer isOpen={navDrawerOpen} onClose={() => setNavDrawerOpen(false)} />
      <MobileProfileDrawer isOpen={profileDrawerOpen} onClose={() => setProfileDrawerOpen(false)} />
    </div>
  );
}
