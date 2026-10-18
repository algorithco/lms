import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useAuth } from '../auth/AuthContext';
import { useLang, type AppLang } from '../i18n/LangContext';
import { useTheme, type Theme } from '../theme/ThemeContext';
import { isPlatformAdmin } from '../lib/api';
import {
  ChevronDownIcon,
  GlobeIcon,
  LogOutIcon,
  MonitorIcon,
  MoonIcon,
  ShieldCheckIcon,
  SunIcon,
  UserIcon,
} from './icons';

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

function getRoleLabel(role?: string, t?: (k: string) => string): string {
  if (role === 'admin') return 'Administrator';
  if (role === 'teacher') return t ? t('role_teacher') : 'Ustoz';
  if (role === 'parent') return t ? t('parent') : 'Ota-ona';
  return t ? t('role_student') : "O'quvchi";
}

export default function UserNavDropdown() {
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useLang();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const isLight = resolvedTheme === 'light';

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  if (!user) return null;

  const initials = getInitials(user.full_name, user.email);
  const isAdmin = isPlatformAdmin(user);

  const handleLogout = async () => {
    setOpen(false);
    await logout();
    navigate('/login');
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Trigger Chip / Pill */}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Foydalanuvchi menyusi"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 10,
          padding: '4px 12px 4px 6px',
          borderRadius: 9999,
          background: open
            ? isLight
              ? '#f1f5f9'
              : 'var(--card-2)'
            : isLight
            ? 'rgba(0, 0, 0, 0.04)'
            : 'rgba(255, 255, 255, 0.05)',
          border: open
            ? '1px solid var(--accent)'
            : isLight
            ? '1px solid #cbd5e1'
            : '1px solid var(--border)',
          color: isLight ? '#0f172a' : 'var(--ink)',
          cursor: 'pointer',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          boxShadow: open ? '0 0 16px rgba(245, 158, 11, 0.2)' : 'none',
        }}
        onMouseEnter={(e) => {
          if (!open) {
            e.currentTarget.style.borderColor = 'var(--border-focus)';
            e.currentTarget.style.background = isLight ? '#f1f5f9' : 'var(--card-2)';
          }
        }}
        onMouseLeave={(e) => {
          if (!open) {
            e.currentTarget.style.borderColor = isLight ? '#cbd5e1' : 'var(--border)';
            e.currentTarget.style.background = isLight ? 'rgba(0, 0, 0, 0.04)' : 'rgba(255, 255, 255, 0.05)';
          }
        }}
      >
        {/* Avatar */}
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={user.full_name || 'Profil'}
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              objectFit: 'cover',
              border: '1.5px solid var(--accent)',
            }}
          />
        ) : (
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #f59e0b, #d97706)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 0.5,
              flexShrink: 0,
            }}
          >
            {initials}
          </span>
        )}

        {/* User Name */}
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            maxWidth: 140,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {user.full_name || user.email}
        </span>

        {/* Animated Chevron Down */}
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          style={{ display: 'inline-flex', alignItems: 'center', color: isLight ? '#64748b' : 'var(--muted)' }}
        >
          <ChevronDownIcon size={14} />
        </motion.span>
      </button>

      {/* Framer Motion Animated Dropdown Menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.96 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            role="menu"
            aria-label="Profil parametrlari"
            style={{
              position: 'absolute',
              top: 'calc(100% + 8px)',
              right: 0,
              width: 290,
              background: isLight ? '#ffffff' : 'var(--dropdown-bg)',
              border: isLight ? '1px solid #e2e8f0' : '1px solid var(--dropdown-border)',
              borderRadius: 16,
              boxShadow: isLight
                ? '0 12px 36px rgba(0, 0, 0, 0.08)'
                : 'var(--card-shadow, 0 16px 40px rgba(0, 0, 0, 0.35))',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              padding: 12,
              zIndex: 1000,
              color: isLight ? '#0f172a' : 'var(--ink)',
            }}
          >
            {/* Header: User Info Card */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 10px 12px',
                borderBottom: isLight ? '1px solid #f1f5f9' : '1px solid var(--border)',
                marginBottom: 8,
              }}
            >
              {user.avatar ? (
                <img
                  src={user.avatar}
                  alt={user.full_name || 'Profil'}
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    objectFit: 'cover',
                    border: '2px solid var(--accent)',
                  }}
                />
              ) : (
                <span
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 15,
                    fontWeight: 800,
                    flexShrink: 0,
                  }}
                >
                  {initials}
                </span>
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <strong
                  style={{
                    display: 'block',
                    fontSize: 14,
                    fontWeight: 700,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    color: isLight ? '#0f172a' : 'var(--ink)',
                  }}
                >
                  {user.full_name || 'Foydalanuvchi'}
                </strong>
                <span
                  style={{
                    display: 'block',
                    fontSize: 12,
                    color: isLight ? '#64748b' : 'var(--muted)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {user.email}
                </span>
                <span
                  style={{
                    display: 'inline-block',
                    marginTop: 4,
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: isAdmin
                      ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.25))'
                      : 'rgba(245, 158, 11, 0.15)',
                    color: isAdmin ? '#fbbf24' : 'var(--accent-dark)',
                    border: isAdmin
                      ? '1px solid rgba(245, 158, 11, 0.45)'
                      : '1px solid rgba(245, 158, 11, 0.25)',
                  }}
                >
                  {isAdmin
                    ? (user.is_superuser ? '🛡️ SUPERADMIN' : '🛡️ ADMIN')
                    : getRoleLabel(user.role, t)}
                </span>
              </div>
            </div>

            {/* Admin Panel Direct Link for Admins */}
            {isAdmin && (
              <Link
                to="/panel"
                onClick={() => setOpen(false)}
                role="menuitem"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '9px 12px',
                  borderRadius: 10,
                  color: '#f59e0b',
                  background: 'rgba(245, 158, 11, 0.12)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  textDecoration: 'none',
                  fontSize: 13,
                  fontWeight: 700,
                  marginBottom: 6,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.22)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.12)')}
              >
                <ShieldCheckIcon size={16} style={{ color: '#f59e0b' }} />
                <span>🛡️ Admin Panel</span>
              </Link>
            )}

            {/* Item 1: Profile & Settings Link */}
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              role="menuitem"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 12px',
                borderRadius: 10,
                color: isLight ? '#0f172a' : 'var(--ink)',
                textDecoration: 'none',
                fontSize: 13,
                fontWeight: 600,
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = isLight ? '#f8fafc' : 'var(--dropdown-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <UserIcon size={16} style={{ color: 'var(--accent)' }} />
              <span>{t('profile_settings_title')}</span>
            </Link>

            {/* Item 2: Language Segmented Switcher */}
            <div style={{ padding: '8px 12px 6px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: isLight ? '#64748b' : 'var(--muted)',
                }}
              >
                <GlobeIcon size={14} />
                <span>{t('select_language_title')}</span>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 4,
                  background: isLight ? '#f1f5f9' : 'var(--card-2)',
                  padding: 3,
                  borderRadius: 10,
                  border: isLight ? '1px solid #e2e8f0' : '1px solid var(--border)',
                }}
              >
                {[
                  { code: 'uz' as AppLang, label: "O'zbekcha (UZ)" },
                  { code: 'ru' as AppLang, label: 'Русский (RU)' },
                  { code: 'en' as AppLang, label: 'English (EN)' },
                ].map((item) => {
                  const isActive = lang === item.code;
                  return (
                    <button
                      key={item.code}
                      type="button"
                      onClick={() => setLang(item.code)}
                      style={{
                        padding: '6px 2px',
                        border: 'none',
                        borderRadius: 7,
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        cursor: 'pointer',
                        background: isActive ? 'var(--accent)' : 'transparent',
                        color: isActive ? '#090d16' : isLight ? '#475569' : 'var(--ink-soft)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {item.code.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Item 3: Theme Switcher (Dark / Light / System) */}
            <div style={{ padding: '6px 12px 8px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: isLight ? '#64748b' : 'var(--muted)',
                }}
              >
                <MoonIcon size={14} />
                <span>{t('select_theme_title')}</span>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 4,
                  background: isLight ? '#f1f5f9' : 'var(--card-2)',
                  padding: 3,
                  borderRadius: 10,
                  border: isLight ? '1px solid #e2e8f0' : '1px solid var(--border)',
                }}
              >
                {[
                  { key: 'dark' as Theme, label: t('theme_dark'), icon: MoonIcon },
                  { key: 'light' as Theme, label: t('theme_light'), icon: SunIcon },
                  { key: 'system' as Theme, label: t('theme_system'), icon: MonitorIcon },
                ].map((item) => {
                  const isActive = theme === item.key;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setTheme(item.key)}
                      title={item.label}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 5,
                        padding: '6px 4px',
                        border: 'none',
                        borderRadius: 7,
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        cursor: 'pointer',
                        background: isActive ? 'var(--accent)' : 'transparent',
                        color: isActive ? '#090d16' : isLight ? '#475569' : 'var(--ink-soft)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <Icon size={12} />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Item 4: Divider */}
            <div
              style={{
                height: 1,
                background: isLight ? '#f1f5f9' : 'var(--border)',
                margin: '6px 0',
              }}
            />

            {/* Item 5: Logout */}
            <button
              type="button"
              onClick={handleLogout}
              role="menuitem"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '9px 12px',
                borderRadius: 10,
                border: 'none',
                background: 'transparent',
                color: isLight ? '#e11d48' : '#f43f5e',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = isLight ? '#fee2e2' : 'rgba(244, 63, 94, 0.12)')
              }
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <LogOutIcon size={16} />
              <span>{t('logout')}</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
