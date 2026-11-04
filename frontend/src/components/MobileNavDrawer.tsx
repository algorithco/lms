import { AnimatePresence, motion } from 'framer-motion';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../theme/ThemeContext';
import { useLang } from '../i18n/LangContext';
import { canReviewEssays, canTeach, isPlatformAdmin } from '../lib/api';
import {
  BarChartIcon,
  CameraIcon,
  CrownIcon,
  FileTextIcon,
  FolderOpenIcon,
  HomeIcon,
  MoonIcon,
  PenLineIcon,
  ShieldCheckIcon,
  SparklesIcon,
  SunIcon,
  SwordsIcon,
  TrophyIcon,
  UsersIcon,
  XIcon,
} from './icons';

interface MobileNavDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export type CategoryTrack = 'milliy' | 'attestatsiya' | 'ielts';

export default function MobileNavDrawer({ isOpen, onClose }: MobileNavDrawerProps) {
  const { user } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useLang();

  const isDark = resolvedTheme === 'dark';
  const isTeacher = canTeach(user);
  const isAdmin = isPlatformAdmin(user);
  const isReviewer = canReviewEssays(user);

  const linkStyle = ({ isActive }: { isActive: boolean }) => ({
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '11px 14px',
    borderRadius: 14,
    textDecoration: 'none',
    fontSize: 14,
    fontWeight: isActive ? 800 : 700,
    color: isActive
      ? '#D97706'
      : isDark
      ? '#E2E8F0'
      : '#1E293B',
    background: isActive
      ? isDark
        ? 'rgba(245, 158, 11, 0.15)'
        : 'rgba(245, 158, 11, 0.12)'
      : 'transparent',
    transition: 'all 0.15s ease',
  });

  return (
    <AnimatePresence>
      {isOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100 }}>
          {/* Backdrop Blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(4, 7, 13, 0.65)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
            aria-hidden="true"
          />

          {/* Slide-over Drawer from Right */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            role="dialog"
            aria-modal="true"
            aria-label={t('nav_menu_label')}
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '85%',
              maxWidth: 350,
              background: isDark ? '#0F172A' : '#FFFFFF',
              color: isDark ? '#F8FAFC' : '#0F172A',
              borderLeft: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #E2E8F0',
              boxShadow: '-12px 0 40px rgba(0, 0, 0, 0.45)',
              display: 'flex',
              flexDirection: 'column',
              overflowY: 'auto',
              padding: '20px 18px',
              zIndex: 101,
            }}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: 14,
                borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #F1F5F9',
                marginBottom: 14,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img
                  src="/logo-mark.png"
                  alt="GRANDEC"
                  style={{ height: 32, width: 'auto', objectFit: 'contain' }}
                />
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontWeight: 900, fontSize: 15, lineHeight: 1.1, color: isDark ? '#F8FAFC' : '#0F172A' }}>
                    GRANDEC
                  </span>
                  <span style={{ fontSize: 8.5, fontWeight: 800, color: '#D97706', letterSpacing: '0.12em' }}>
                    ACADEMIC EDTECH
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Yopish"
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: isDark ? 'rgba(255, 255, 255, 0.06)' : '#F1F5F9',
                  border: 'none',
                  color: isDark ? '#94A3B8' : '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}
              >
                <XIcon size={18} />
              </button>
            </div>

            {/* Main Navigation List */}
            <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
              <p
                style={{
                  margin: '8px 0 4px',
                  fontSize: 11,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: isDark ? '#94A3B8' : '#64748B',
                }}
              >
                {t('nav_sec_main')}
              </p>

              <NavLink to="/dashboard" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#F59E0B' }}><HomeIcon size={18} /></span>
                <span>{t('nav_home')}</span>
              </NavLink>

              <NavLink to="/tests" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#059669' }}><FileTextIcon size={18} /></span>
                <span>{t('nav_tests')}</span>
              </NavLink>

              <NavLink to="/essays" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#0284C7' }}><PenLineIcon size={18} /></span>
                <span>{t('nav_essays')}</span>
              </NavLink>

              <NavLink to="/arena" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#DC2626' }}><SwordsIcon size={18} /></span>
                <span>{t('nav_arena')}</span>
              </NavLink>

              <NavLink to="/tests/scan-omr" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#8B5CF6' }}><CameraIcon size={18} /></span>
                <span>{t('nav_omr')}</span>
              </NavLink>

              <NavLink to="/results" style={linkStyle} onClick={onClose}>
                <span style={{ color: '#D97706' }}><TrophyIcon size={18} /></span>
                <span>{t('nav_results')}</span>
              </NavLink>

              {!isAdmin && (
                <NavLink to="/subscribe" style={linkStyle} onClick={onClose}>
                  <span style={{ color: '#F59E0B' }}><CrownIcon size={18} /></span>
                  <span>{t('drawer_plans')}</span>
                </NavLink>
              )}

              {/* Role-Specific Sections */}
              {isTeacher && (
                <>
                  <p
                    style={{
                      margin: '14px 0 4px',
                      fontSize: 11,
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      color: isDark ? '#94A3B8' : '#64748B',
                    }}
                  >
                    {t('nav_sec_teacher')}
                  </p>
                  <NavLink to="/teacher" end style={linkStyle} onClick={onClose}>
                    <UsersIcon size={18} />
                    <span>{t('nav_students')}</span>
                  </NavLink>
                  <NavLink to="/groups" style={linkStyle} onClick={onClose}>
                    <FolderOpenIcon size={18} />
                    <span>{t('tf_groups')}</span>
                  </NavLink>
                  <NavLink to="/teacher/ai-converter" style={linkStyle} onClick={onClose}>
                    <SparklesIcon size={18} />
                    <span>{t('nav_converter')}</span>
                  </NavLink>
                  <NavLink to="/analytics" style={linkStyle} onClick={onClose}>
                    <BarChartIcon size={18} />
                    <span>{t('nav_analytics')}</span>
                  </NavLink>
                  {isReviewer && (
                    <NavLink to="/teacher/essays" style={linkStyle} onClick={onClose}>
                      <PenLineIcon size={18} />
                      <span>{t('nav_review_queue')}</span>
                    </NavLink>
                  )}
                </>
              )}

              {isAdmin && (
                <>
                  <p
                    style={{
                      margin: '14px 0 4px',
                      fontSize: 11,
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      color: '#EF4444',
                    }}
                  >
                    {t('drawer_admin_panel')}
                  </p>
                  <NavLink to="/panel" end style={linkStyle} onClick={onClose}>
                    <ShieldCheckIcon size={18} style={{ color: '#EF4444' }} />
                    <span>{t('nav_admin')}</span>
                  </NavLink>
                </>
              )}
            </nav>

            {/* Bottom Actions: Theme Toggle & Telegram Bot */}
            <div
              style={{
                borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
                paddingTop: 14,
                marginTop: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              {/* Theme Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isDark ? <MoonIcon size={16} style={{ color: '#F59E0B' }} /> : <SunIcon size={16} style={{ color: '#F59E0B' }} />}
                  <span>{t('drawer_theme')}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setTheme(isDark ? 'light' : 'dark')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 10,
                    fontSize: 12,
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: isDark ? 'rgba(245, 158, 11, 0.15)' : '#F1F5F9',
                    color: isDark ? '#F59E0B' : '#0F172A',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  {isDark ? t('nav_theme_dark') : t('nav_theme_light')}
                </button>
              </div>

              {/* Telegram Bot Link */}
              <a
                href="https://t.me/uz_essaygrader_bot"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '10px 14px',
                  borderRadius: 12,
                  background: 'rgba(2, 132, 199, 0.1)',
                  color: '#0284C7',
                  border: '1px solid rgba(2, 132, 199, 0.25)',
                  fontSize: 13,
                  fontWeight: 700,
                  textDecoration: 'none',
                }}
              >
                <span>✈️</span>
                <span>{t('nav_tg_bot')}</span>
              </a>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
