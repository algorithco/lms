import { useState, useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, canViewParent, isPlatformAdmin, GamificationApi, type StreakInfoResponse } from '../lib/api';
import UserNavDropdown from './UserNavDropdown';
import { Flame } from 'lucide-react';
import PlanBadge from './PlanBadge';
import { useSubject } from '../lib/useSubject';
import { formatDisplayName, initialsOf } from '../lib/displayName';
import MobileBottomBar from './MobileBottomBar';
import MobileNavDrawer from './MobileNavDrawer';
import MobileProfileDrawer from './MobileProfileDrawer';
import SubjectSwitcher from './SubjectSwitcher';
import {
  BarChartIcon,
  CameraIcon,
  CreditCardIcon,
  FileTextIcon,
  FolderOpenIcon,
  HomeIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MicIcon,
  PenLineIcon,
  ShieldCheckIcon,
  SparklesIcon,
  SwordsIcon,
  TrophyIcon,
  UploadIcon,
  UserPlusIcon,
  UsersIcon,
} from './icons';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `nav-link side-link${isActive ? ' active' : ''}`;

/** /tests/create and /tests/scan-omr have their own menu items: "Tests" is not lit on them as well. */
const OWN_TEST_ITEMS = ['/tests/create', '/tests/scan-omr'];
const testsLinkClass = (pathname: string) => ({ isActive }: { isActive: boolean }) =>
  linkClass({ isActive: isActive && !OWN_TEST_ITEMS.some((p) => pathname.startsWith(p)) });

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <p className="side-section">{title}</p>
      {children}
    </>
  );
}

/** Phone top bar title per route (first match wins). */
const PAGE_TITLES: [string, string][] = [
  ['/dashboard', 'tb_title_home'],
  ['/tests/scan-omr', 'titul_scanner'],
  ['/tests', 'tests'],
  ['/take', 'tests'],
  ['/essays', 'tb_title_essays'],
  ['/results', 'results_analysis'],
  ['/arena', 'arena'],
  ['/profile', 'tb_title_profile'],
  ['/groups', 'groups'],
  ['/speaking', 'tb_title_speaking'],
  ['/subscribe', 'pay_plans_title'],
  ['/plans', 'pay_plans_title'],
  ['/checkout', 'pay_plans_title'],
  ['/my-subscription', 'pay_current_sub'],
  ['/certificates', 'certificates'],
  ['/games', 'games'],
  ['/teacher', 'teacher_cabinet'],
  ['/panel', 'tb_admin_panel'],
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [streakData, setStreakData] = useState<StreakInfoResponse | null>(null);
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const [profileDrawerOpen, setProfileDrawerOpen] = useState(false);
  const activeSubject = useSubject();
  const { pathname } = useLocation();
  const titleKey = PAGE_TITLES.find(([prefix]) => pathname.startsWith(prefix))?.[1];
  const pageTitle = titleKey ? t(titleKey) : 'GRANDEC';

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
              <NavLink to="/tests" className={testsLinkClass(pathname)} onClick={close}>
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
            <NavLink to="/tests" className={testsLinkClass(pathname)} onClick={close}>
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

          <PlanBadge variant="card" onNavigate={close} />
        </nav>
        <div className="side-user">
          <span className="avatar">{initialsOf(user?.full_name, user?.email)}</span>
          <span className="side-user-meta">
            <strong>{formatDisplayName(user?.full_name, user?.email) || t('user_default')}</strong>
            <small>{user?.role}</small>
          </span>
          <button className="btn ghost sm" onClick={onLogout} title={t('logout')} aria-label={t('logout')}><LogOutIcon size={14} className="ico" /></button>
        </div>
      </aside>
      {open && <div className="overlay" onClick={close} aria-hidden="true" />}

      <div className="main">
        <header className="topbar app-topbar" aria-label={t('topbar_label')}>
          <div className="topbar-inner">
            {/* Phones: logo + page title on the left (the sidebar carries the brand on desktop). */}
            <Link to="/dashboard" className="tb-brand md:hidden">
              <img src="/logo-mark.png" alt="" width={28} height={28} />
              <span className="tb-title">{pageTitle}</span>
            </Link>

            <div className="hidden md:flex">
              {user?.active_subject && (
                <span className="tb-tag">{t(activeSubject === 'english' ? 'app_motto_badge_english' : 'app_motto_badge')}</span>
              )}
            </div>
            <div className="spacer" />
            <div className="tb-right">
              {streakData && (
                <span
                  className="tb-xp"
                  title={t('tb_streak_title')
                    .replace('{days}', String(streakData.current_streak))
                    .replace('{xp}', String(streakData.xp_points))}
                >
                  <Flame size={14} aria-hidden="true" className={streakData.is_active_today ? 'is-hot' : ''} />
                  <span>{streakData.current_streak}</span>
                  <span className="tb-xp__sep" aria-hidden="true">·</span>
                  <span>{streakData.xp_points} XP</span>
                </span>
              )}
              <div className="hidden md:flex">
                <SubjectSwitcher size="sm" />
              </div>
              <div className="hidden md:flex" style={{ alignItems: 'center', gap: 8 }}>
                {isAdmin && (
                  <Link to="/panel" className="ui-btn ui-btn--sm">
                    <ShieldCheckIcon size={14} />
                    <span>{t('tb_admin_panel')}</span>
                  </Link>
                )}
                <UserNavDropdown />
              </div>
              <button
                type="button"
                className="tb-avatar md:hidden"
                onClick={() => setProfileDrawerOpen(true)}
                aria-label={t('tb_open_profile')}
              >
                {user?.avatar ? <img src={user.avatar} alt="" /> : <span>{initialsOf(user?.full_name, user?.email)}</span>}
              </button>
            </div>
          </div>
        </header>
        {/* Phones: subject switcher as a segmented control under the bar (never inside it). */}
        <div className="tb-subject md:hidden">
          <SubjectSwitcher variant="seg" />
        </div>
        <main className="content">
          <Outlet />
        </main>
      </div>

      {/* TESTMAKON-STYLE 3D SOFT BOTTOM NAVIGATION & DRAWERS */}
      <MobileBottomBar onOpenProfile={() => setProfileDrawerOpen(true)} />
      <MobileNavDrawer isOpen={navDrawerOpen} onClose={() => setNavDrawerOpen(false)} />
      <MobileProfileDrawer
        isOpen={profileDrawerOpen}
        onClose={() => setProfileDrawerOpen(false)}
        onOpenMenu={() => {
          setProfileDrawerOpen(false);
          setNavDrawerOpen(true);
        }}
      />
    </div>
  );
}
