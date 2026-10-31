import { AnimatePresence, motion } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang, type AppLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { isPlatformAdmin, formatDisplayName } from '../lib/api';
import {
  CrownIcon,
  GlobeIcon,
  LogOutIcon,
  MoonIcon,
  ShieldCheckIcon,
  SunIcon,
  TrophyIcon,
  UserIcon,
  XIcon,
} from './icons';

interface MobileProfileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

function getInitials(name?: string, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email && email.trim()) {
    return email.slice(0, 2).toUpperCase();
  }
  return 'U';
}

function getRoleBadge(role?: string): { label: string; bg: string; color: string } {
  if (role === 'admin' || role === 'superadmin') {
    return { label: '🛡 Administrator', bg: 'rgba(239, 68, 68, 0.12)', color: '#EF4444' };
  }
  if (role === 'teacher') {
    return { label: "👨‍🏫 O'qituvchi / Ustoz", bg: 'rgba(16, 185, 129, 0.12)', color: '#10B981' };
  }
  if (role === 'parent') {
    return { label: '👨‍👩‍👧 Ota-ona', bg: 'rgba(59, 130, 246, 0.12)', color: '#3B82F6' };
  }
  return { label: "🎓 O'quvchi", bg: 'rgba(245, 158, 11, 0.12)', color: '#F59E0B' };
}

export default function MobileProfileDrawer({ isOpen, onClose }: MobileProfileDrawerProps) {
  const { user, logout, openAuthModal } = useAuth();
  const { lang, setLang, t } = useLang();
  const { resolvedTheme, setTheme } = useTheme();
  const navigate = useNavigate();

  const isDark = resolvedTheme === 'dark';

  const handleLogout = async () => {
    onClose();
    await logout();
    navigate('/login');
  };

  const initials = getInitials(user?.full_name, user?.email);
  const roleBadge = getRoleBadge(user?.role);
  const isAdmin = user ? isPlatformAdmin(user) : false;

  const isTelegramUser =
    Boolean(
      user?.email?.includes('tg_') ||
      user?.email?.includes('@tma') ||
      (user as unknown as Record<string, unknown> | undefined)?.telegram_id
    );

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
            aria-label="Foydalanuvchi profili"
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '85%',
              maxWidth: 360,
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
                paddingBottom: 16,
                borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #F1F5F9',
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 18 }}>👤</span>
                <strong style={{ fontSize: 16, fontWeight: 900 }}>Mening Profilim</strong>
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

            {user ? (
              <>
                {/* User Card */}
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: isDark
                      ? 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)'
                      : 'linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%)',
                    border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
                    marginBottom: 18,
                    textAlign: 'center',
                    boxShadow: isDark ? '0 4px 20px rgba(0, 0, 0, 0.3)' : '0 4px 15px rgba(0, 0, 0, 0.03)',
                  }}
                >
                  {/* Large Avatar */}
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
                    {user.avatar ? (
                      <img
                        src={user.avatar}
                        alt={user.full_name || 'Profil'}
                        style={{
                          width: 64,
                          height: 64,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          border: '3px solid #F59E0B',
                          boxShadow: '0 4px 14px rgba(245, 158, 11, 0.3)',
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 64,
                          height: 64,
                          borderRadius: '50%',
                          background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                          color: '#FFFFFF',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 22,
                          fontWeight: 900,
                          boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)',
                        }}
                      >
                        {initials}
                      </div>
                    )}
                  </div>

                  {/* Name */}
                  <h3
                    style={{
                      margin: '0 0 4px',
                      fontSize: 17,
                      fontWeight: 900,
                      color: isDark ? '#F8FAFC' : '#0F172A',
                    }}
                  >
                    {formatDisplayName(user.full_name, user.email)}
                  </h3>

                  {/* Synthetic Email / Telegram Badge */}
                  <p
                    style={{
                      margin: '0 0 10px',
                      fontSize: 12,
                      color: isDark ? '#94A3B8' : '#64748B',
                      fontWeight: 600,
                    }}
                  >
                    {isTelegramUser ? (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          color: '#0284C7',
                          fontWeight: 700,
                        }}
                      >
                        <span>📱 Telegram SSO</span>
                      </span>
                    ) : (
                      user.email
                    )}
                  </p>

                  {/* Badges: Role, Plan, ID */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: 20,
                        fontSize: 11,
                        fontWeight: 800,
                        background: roleBadge.bg,
                        color: roleBadge.color,
                      }}
                    >
                      {roleBadge.label}
                    </span>

                    {user.is_paid && user.plan && user.plan.toUpperCase() !== 'FREE' ? (
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 800,
                          background: 'rgba(245, 158, 11, 0.15)',
                          color: '#D97706',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <CrownIcon size={12} />
                        {user.plan.toUpperCase()}
                      </span>
                    ) : (
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 700,
                          background: 'rgba(148, 163, 184, 0.15)',
                          color: isDark ? '#94A3B8' : '#64748B',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        BEPUL
                      </span>
                    )}

                    <span
                      style={{
                        padding: '4px 8px',
                        borderRadius: 20,
                        fontSize: 11,
                        fontWeight: 700,
                        background: isDark ? 'rgba(255, 255, 255, 0.08)' : '#E2E8F0',
                        color: isDark ? '#94A3B8' : '#475569',
                      }}
                    >
                      #ID-{user.id || '2026'}
                    </span>
                  </div>
                </div>

                {/* Navigation Items */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20, flex: 1 }}>
                  <Link
                    to="/profile"
                    onClick={onClose}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '11px 14px',
                      borderRadius: 12,
                      textDecoration: 'none',
                      color: isDark ? '#F1F5F9' : '#1E293B',
                      background: isDark ? 'rgba(255, 255, 255, 0.03)' : '#F8FAFC',
                      fontWeight: 700,
                      fontSize: 14,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span style={{ color: '#F59E0B' }}><UserIcon size={18} /></span>
                    <span>Shaxsiy Kabinet va Ma&apos;lumotlar</span>
                  </Link>

                  <Link
                    to="/certificates"
                    onClick={onClose}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '11px 14px',
                      borderRadius: 12,
                      textDecoration: 'none',
                      color: isDark ? '#F1F5F9' : '#1E293B',
                      background: isDark ? 'rgba(255, 255, 255, 0.03)' : '#F8FAFC',
                      fontWeight: 700,
                      fontSize: 14,
                    }}
                  >
                    <span style={{ color: '#10B981' }}><TrophyIcon size={18} /></span>
                    <span>Mening Sertifikatlarim</span>
                  </Link>

                  <Link
                    to="/subscribe"
                    onClick={onClose}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '11px 14px',
                      borderRadius: 12,
                      textDecoration: 'none',
                      color: isDark ? '#F1F5F9' : '#1E293B',
                      background: isDark ? 'rgba(255, 255, 255, 0.03)' : '#F8FAFC',
                      fontWeight: 700,
                      fontSize: 14,
                    }}
                  >
                    <span style={{ color: '#D97706' }}><CrownIcon size={18} /></span>
                    <span>Tariflar va Obuna (PRO)</span>
                  </Link>

                  {isAdmin && (
                    <Link
                      to="/panel"
                      onClick={onClose}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: '11px 14px',
                        borderRadius: 12,
                        textDecoration: 'none',
                        color: '#EF4444',
                        background: 'rgba(239, 68, 68, 0.08)',
                        fontWeight: 800,
                        fontSize: 14,
                      }}
                    >
                      <ShieldCheckIcon size={18} />
                      <span>Admin Boshqaruv Paneli</span>
                    </Link>
                  )}
                </div>
              </>
            ) : (
              /* Guest State */
              <div style={{ padding: '24px 12px', textAlign: 'center', flex: 1 }}>
                <div style={{ fontSize: 42, marginBottom: 12 }}>✨</div>
                <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900 }}>Xush kelibsiz!</h3>
                <p style={{ margin: '0 0 24px', fontSize: 13, color: '#64748B', lineHeight: 1.5 }}>
                  Imtihonlarga tayyorgarlik ko&apos;rish va natijalaringizni saqlash uchun tizimga kiring.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      openAuthModal('login');
                    }}
                    style={{
                      padding: '12px 20px',
                      borderRadius: 12,
                      background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                      color: '#FFFFFF',
                      fontWeight: 800,
                      fontSize: 14,
                      border: 'none',
                      cursor: 'pointer',
                      boxShadow: '0 4px 14px rgba(217, 119, 6, 0.3)',
                    }}
                  >
                    1-klikda kirish
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      openAuthModal('register');
                    }}
                    style={{
                      padding: '11px 20px',
                      borderRadius: 12,
                      background: isDark ? 'rgba(255, 255, 255, 0.06)' : '#F1F5F9',
                      color: isDark ? '#F8FAFC' : '#0F172A',
                      fontWeight: 800,
                      fontSize: 14,
                      border: '1px solid #E2E8F0',
                      cursor: 'pointer',
                    }}
                  >
                    Ro&apos;yxatdan o&apos;tish
                  </button>
                </div>
              </div>
            )}

            {/* Bottom Controls: Language, Theme & Logout */}
            <div
              style={{
                borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
                paddingTop: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {/* Language Switcher */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <GlobeIcon size={16} style={{ color: '#0284C7' }} />
                  <span>Til:</span>
                </span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['uz', 'en', 'ru'] as AppLang[]).map((l) => (
                    <button
                      key={l}
                      type="button"
                      onClick={() => setLang(l)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 8,
                        fontSize: 11,
                        fontWeight: 800,
                        border: 'none',
                        cursor: 'pointer',
                        background: lang === l ? '#F59E0B' : isDark ? 'rgba(255, 255, 255, 0.06)' : '#F1F5F9',
                        color: lang === l ? '#FFFFFF' : isDark ? '#94A3B8' : '#64748B',
                      }}
                    >
                      {l.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Theme Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isDark ? <MoonIcon size={16} style={{ color: '#F59E0B' }} /> : <SunIcon size={16} style={{ color: '#F59E0B' }} />}
                  <span>Rejim:</span>
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
                  {isDark ? '🌙 Tungi' : '☀️ Kunduzgi'}
                </button>
              </div>

              {/* Logout Button */}
              {user && (
                <button
                  type="button"
                  onClick={handleLogout}
                  style={{
                    marginTop: 8,
                    padding: '11px 16px',
                    borderRadius: 12,
                    background: 'rgba(239, 68, 68, 0.08)',
                    color: '#EF4444',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    fontWeight: 800,
                    fontSize: 13.5,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    cursor: 'pointer',
                  }}
                >
                  <LogOutIcon size={16} />
                  <span>{t('logout')}</span>
                </button>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
