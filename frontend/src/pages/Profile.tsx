import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang, type AppLang } from '../i18n/LangContext';
import { useTranslation } from '../i18n/useTranslation';
import { useTheme, type Theme } from '../theme/ThemeContext';
import { isPlatformAdmin, ProfileApi } from '../lib/api';
import {
  MonitorIcon,
  MoonIcon,
  SunIcon,
  UserIcon,
} from '../components/icons';
import UsageLimits from '../components/UsageLimits';
import ParentMonitoringCard from '../components/ParentMonitoringCard';

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

export default function Profile() {
  const { user, updateUserLocal } = useAuth();
  const { lang, setLang } = useLang();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { t } = useTranslation();

  const [telegramId, setTelegramId] = useState(
    user?.telegram_chat_id ? String(user.telegram_chat_id) : (isPlatformAdmin(user) ? '5582178765' : '')
  );
  const [tgLoading, setTgLoading] = useState(false);
  const [tgSuccess, setTgSuccess] = useState<string | null>(null);
  const [tgError, setTgError] = useState<string | null>(null);

  const handleLinkTelegram = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!telegramId.trim()) {
      setTgError('Iltimos, Telegram ID raqamingizni kiriting.');
      return;
    }
    const parsedId = Number(telegramId.trim());
    if (!Number.isFinite(parsedId) || parsedId <= 0) {
      setTgError('Telegram ID musbat son bo‘lishi kerak.');
      return;
    }
    setTgLoading(true);
    setTgError(null);
    setTgSuccess(null);
    try {
      const res = await ProfileApi.linkTelegram(parsedId);
      setTgSuccess(res.message || 'Telegram hisobi muvaffaqiyatli bog‘landi!');
      updateUserLocal({ telegram_chat_id: res.telegram_chat_id });
    } catch (err) {
      setTgError(err instanceof Error ? err.message : 'Bog‘lashda server xatoligi yuz berdi.');
    } finally {
      setTgLoading(false);
    }
  };

  if (!user) return null;

  const initials = getInitials(user.full_name, user.email);

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', paddingBottom: 60 }}>
      {/* Header Card with User Avatar & Info */}
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          padding: 24,
          marginBottom: 24,
          background: 'linear-gradient(135deg, var(--card), var(--card-2))',
          flexWrap: 'wrap',
        }}
      >
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={user.full_name || 'Profil'}
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              objectFit: 'cover',
              border: '3px solid var(--accent)',
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3)',
            }}
          />
        ) : (
          <span
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #f59e0b, #d97706)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 26,
              fontWeight: 800,
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3)',
              flexShrink: 0,
            }}
          >
            {initials}
          </span>
        )}

        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>
              {user.full_name || 'Foydalanuvchi'}
            </h1>
            {isPlatformAdmin(user) ? (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  padding: '3px 12px',
                  borderRadius: 20,
                  background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.25))',
                  color: '#fbbf24',
                  border: '1px solid rgba(245, 158, 11, 0.5)',
                  boxShadow: '0 2px 8px rgba(245, 158, 11, 0.2)',
                }}
              >
                🛡️ {user.is_superuser ? "TO'LIQ HUQUQLI SUPERADMIN" : "ADMIN"}
              </span>
            ) : (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '3px 10px',
                  borderRadius: 20,
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: 'var(--accent-dark)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                {user.role}
              </span>
            )}
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: '3px 10px',
                borderRadius: 20,
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}
            >
              {t('profile_active_account')}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6, flexWrap: 'wrap' }}>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              {user.email}
            </p>
            {isPlatformAdmin(user) && (
              <Link
                to="/panel"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 12px',
                  borderRadius: 8,
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid rgba(245, 158, 11, 0.35)',
                  color: '#f59e0b',
                  fontSize: 12,
                  fontWeight: 700,
                  textDecoration: 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>🛡️ Admin Panelga o'tish →</span>
              </Link>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {/* Personal Details Card */}
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserIcon size={20} style={{ color: 'var(--accent)' }} />
            {t('profile_personal_info')}
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>{t('profile_full_name')}</span>
              <strong style={{ fontSize: 15 }}>{user.full_name || '—'}</strong>
            </div>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>{t('profile_email')}</span>
              <strong style={{ fontSize: 15 }}>{user.email}</strong>
            </div>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>{t('profile_role')}</span>
              <strong style={{ fontSize: 15, textTransform: 'capitalize' }}>{user.role}</strong>
            </div>
          </div>
        </div>

        {/* Interface & Theme Settings Card */}
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <MoonIcon size={20} style={{ color: 'var(--accent)' }} />
            {t('profile_interface_settings')}
          </h2>

          {/* Theme Selector */}
          <div style={{ marginBottom: 20 }}>
            <span className="muted small" style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>
              {t('profile_theme_label')}
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
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
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      padding: '12px 8px',
                      borderRadius: 12,
                      cursor: 'pointer',
                      border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
                      background: isActive ? 'var(--card-2)' : 'transparent',
                      color: isActive ? 'var(--accent-dark)' : 'var(--ink)',
                      fontWeight: isActive ? 700 : 500,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Icon size={18} />
                    <span style={{ fontSize: 12 }}>{item.label}</span>
                  </button>
                );
              })}
            </div>
            <span className="muted small" style={{ display: 'block', marginTop: 6 }}>
              {t('profile_active_theme')}{' '}
              <strong>{resolvedTheme === 'dark' ? t('profile_dark_ui') : t('profile_light_ui')}</strong>
            </span>
          </div>

          {/* Language Selector */}
          <div>
            <span className="muted small" style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>
              {t('profile_lang_label')}
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { code: 'uz' as AppLang, label: "O'zbekcha" },
                { code: 'ru' as AppLang, label: 'Русский' },
                { code: 'en' as AppLang, label: 'English' },
              ].map((item) => {
                const isActive = lang === item.code;
                return (
                  <button
                    key={item.code}
                    type="button"
                    onClick={() => setLang(item.code)}
                    style={{
                      padding: '10px 8px',
                      borderRadius: 12,
                      cursor: 'pointer',
                      border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
                      background: isActive ? 'var(--card-2)' : 'transparent',
                      color: isActive ? 'var(--accent-dark)' : 'var(--ink)',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: 12,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Telegram Account Linking Card */}
      <div
        className="card"
        style={{
          marginTop: 24,
          padding: 24,
          background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, rgba(99, 102, 241, 0.05) 100%)',
          border: '1px solid rgba(14, 165, 233, 0.35)',
          borderRadius: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: 'rgba(14, 165, 233, 0.2)',
                color: '#38bdf8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
              }}
            >
              ✈️
            </div>
            <div>
              <h2 style={{ fontSize: 18, margin: 0, fontWeight: 800 }}>Telegram Hisobini Bog'lash</h2>
              <p className="muted small" style={{ margin: '2px 0 0' }}>
                To'lov kvitansiyalari, davomat hisobotlari va platforma yangiliklari to'g'ridan-to'g'ri Telegramingizga keladi.
              </p>
            </div>
          </div>
          {user.telegram_chat_id ? (
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                padding: '4px 12px',
                borderRadius: 20,
                background: 'rgba(16, 185, 129, 0.2)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.4)',
              }}
            >
              🟢 Faol bog'langan: #{user.telegram_chat_id}
            </span>
          ) : (
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                padding: '4px 12px',
                borderRadius: 20,
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#f59e0b',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              ⚠️ Hali bog'lanmagan
            </span>
          )}
        </div>

        {tgSuccess && (
          <div
            style={{
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#10b981',
              padding: '10px 16px',
              borderRadius: 10,
              marginBottom: 14,
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            ✅ {tgSuccess}
          </div>
        )}

        {tgError && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#f87171',
              padding: '10px 16px',
              borderRadius: 10,
              marginBottom: 14,
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            ⚠️ {tgError}
          </div>
        )}

        <form onSubmit={handleLinkTelegram} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: '1 1 260px' }}>
            <input
              type="text"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
              placeholder="Masalan: 5582178765"
              required
              style={{ width: '100%', fontWeight: 700, letterSpacing: '0.5px' }}
            />
          </div>
          <button
            type="submit"
            disabled={tgLoading}
            className="btn primary sm"
            style={{ fontWeight: 800, minWidth: 160 }}
          >
            {tgLoading ? 'Bog‘lanmoqda…' : user.telegram_chat_id ? '🔄 ID ni Yangilash' : '🔗 Telegramni Bog‘lash'}
          </button>
        </form>
        <span className="muted small" style={{ display: 'block', marginTop: 8 }}>
          💡 Telegram chat ID raqamingizni <strong>@userinfobot</strong> yoki <strong>@getmyid_bot</strong> orqali bilib olishingiz mumkin.
        </span>
      </div>

      {/* Parent Monitoring Smart Alerts */}
      <div style={{ marginTop: 24 }}>
        <ParentMonitoringCard />
      </div>

      {/* Subscription & Usage Limits */}
      <div style={{ marginTop: 24 }}>
        <UsageLimits />
      </div>

      {/* Quick Nav Card */}
      <div
        className="card"
        style={{
          marginTop: 24,
          padding: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <strong style={{ display: 'block', fontSize: 15 }}>{t('profile_manage_sub')}</strong>
          <span className="muted small">{t('profile_view_plans_receipts')}</span>
        </div>
        <Link to="/subscribe" className="btn primary sm btn-glow" style={{ textDecoration: 'none' }}>
          {t('profile_view_plans_btn')}
        </Link>
      </div>
    </div>
  );
}
